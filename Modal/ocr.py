"""
ocr.py - Handwritten/Scanned STEM Document OCR Pipeline
=========================================================
Uses Gemini Vision for:
- Page quality detection
- Region classification (text, math, chemistry, biology, physics, etc.)
- Transcription (text → plain, equations → LaTeX, formulas → LaTeX)
- Visual evaluation (diagrams evaluated directly as images)
- Bilingual feedback generation

Architecture:
  Page image → Quality check → Region detection → 
  Path A (transcribable) or Path B (visual) → 
  Unified annotation schema
"""

import os
import re
import json
import base64
import tempfile
from pathlib import Path
from typing import Optional
import fitz  # PyMuPDF

from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")

# ── Gemini client setup ────────────────────────────────────────────────────
try:
    from google import genai
    from google.genai import types as genai_types
    _client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
    _gemini_available = _client is not None
except ImportError:
    _client = None
    _gemini_available = False


# ── Helpers ────────────────────────────────────────────────────────────────

def _page_to_png_bytes(page: fitz.Page, dpi: int = 150) -> bytes:
    """Render a PDF page to PNG bytes at the given DPI."""
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    pix    = page.get_pixmap(matrix=matrix, alpha=False)
    return pix.tobytes("png")


def _image_file_to_png_bytes(file_content: bytes, filename: str) -> bytes:
    """
    Convert any image format to PNG bytes.
    Falls back to returning original bytes if conversion fails.
    """
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(file_content)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return file_content


def _bytes_to_base64_url(image_bytes: bytes, mime: str = "image/png") -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _call_gemini_vision(image_bytes: bytes, prompt: str) -> Optional[dict]:
    """
    Send a page image to Gemini Vision with a prompt.
    Returns parsed JSON dict or None on failure.
    """
    if not _gemini_available:
        return None

    try:
        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                genai_types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                prompt,
            ],
        )
        text = response.text.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            text = re.sub(r"```(?:json)?", "", text).strip("` \n")

        return json.loads(text)

    except json.JSONDecodeError:
        # Gemini returned non-JSON — return as raw text
        return {"raw_text": response.text.strip()}
    except Exception as e:
        return {"error": str(e)}


# ── STEP 1: Page Quality Detection ────────────────────────────────────────

def detect_page_quality(image_bytes: bytes) -> dict:
    """
    Assess how readable a scanned/handwritten page is.
    Returns quality level and confidence score.
    """
    prompt = """
Assess the readability of this handwritten or scanned document page.

Consider:
- Clarity of handwriting
- Scan quality (brightness, contrast, skew)
- Ink visibility
- Whether diagrams and text are distinguishable

Respond ONLY with valid JSON:
{
  "confidence": 0.85,
  "quality_level": "clear",
  "issues": [],
  "readable_percentage": 90,
  "recommendation": "Process normally"
}

quality_level must be exactly one of:
- "clear"     → confidence > 0.80, process normally
- "partial"   → confidence 0.40-0.80, process with warnings
- "poor"      → confidence 0.20-0.40, attempt with heavy caveats
- "unreadable" → confidence < 0.20, skip this page

issues: list any problems found (e.g. "blurry", "skewed", "low contrast")
Return ONLY the JSON, no other text.
"""
    result = _call_gemini_vision(image_bytes, prompt)
    if not result or "error" in result:
        return {
            "confidence":        0.5,
            "quality_level":     "partial",
            "issues":            ["Quality detection failed"],
            "readable_percentage": 50,
            "recommendation":    "Process with caution",
        }
    return result


# ── STEP 2: Region Detection and Classification ────────────────────────────

def detect_regions(image_bytes: bytes) -> list:
    """
    Detect and classify all content regions on the page.
    Returns list of regions with type, position, and content hints.
    """
    prompt = """
Analyze this handwritten/scanned STEM document page carefully.
Identify every distinct content region and classify it.

Region types:
- "text"                 → plain handwritten text, sentences, explanations
- "math_equation"        → algebraic, calculus, statistics, matrix equations
- "chemical_formula"     → simple chemical formulas (H2SO4, 2H2 + O2 → 2H2O)
- "chemical_structure"   → benzene rings, structural formulas, Newman projections, reaction mechanisms
- "biology_diagram"      → cell diagrams, organ diagrams, neuron, respiratory system, DNA, punnett squares
- "physics_diagram"      → free body diagrams, circuit diagrams, ray diagrams, wave diagrams, vectors
- "engineering_diagram"  → flowcharts, schematics, block diagrams, mechanical drawings
- "graph_plot"           → hand-drawn graphs, charts, scatter plots, phase diagrams
- "table"                → tabular data written by hand

For EACH region provide:
- type (from list above)
- y_start: top edge as fraction of page height (0.0 to 1.0)
- y_end: bottom edge as fraction of page height (0.0 to 1.0)
- x_start: left edge as fraction of page width (0.0 to 1.0)
- x_end: right edge as fraction of page width (0.0 to 1.0)
- description: one sentence describing what you see
- transcribable: true if text/LaTeX can represent it, false if visual evaluation needed

Respond ONLY with a valid JSON array:
[
  {
    "type": "text",
    "y_start": 0.0,
    "y_end": 0.15,
    "x_start": 0.05,
    "x_end": 0.95,
    "description": "Student name and heading",
    "transcribable": true
  },
  {
    "type": "biology_diagram",
    "y_start": 0.20,
    "y_end": 0.65,
    "x_start": 0.05,
    "x_end": 0.95,
    "description": "Hand-drawn neuron diagram with labels",
    "transcribable": false
  }
]

Return ONLY the JSON array, no other text.
"""
    result = _call_gemini_vision(image_bytes, prompt)

    if isinstance(result, list):
        return result

    # Fallback — treat whole page as text
    return [{
        "type":           "text",
        "y_start":        0.0,
        "y_end":          1.0,
        "x_start":        0.0,
        "x_end":          1.0,
        "description":    "Full page content",
        "transcribable":  True,
    }]


# ── STEP 3A: Transcription (Path A — text/equations) ──────────────────────

def transcribe_region(image_bytes: bytes, region: dict) -> dict:
    """
    Transcribe a text/equation/formula region.
    Returns transcribed content in appropriate format.
    """
    region_type = region.get("type", "text")

    if region_type == "math_equation":
        format_instruction = """
Transcribe all mathematical content as LaTeX.
Use standard LaTeX notation:
- Fractions: \\frac{numerator}{denominator}
- Integrals: \\int_{a}^{b}
- Summations: \\sum_{i=0}^{n}
- Square roots: \\sqrt{x}
- Greek letters: \\alpha, \\beta, \\gamma
- Matrices: \\begin{matrix}...\\end{matrix}
"""
    elif region_type == "chemical_formula":
        format_instruction = """
Transcribe chemical content as LaTeX:
- Subscripts for numbers: H_2O, H_2SO_4
- Arrows: \\rightarrow for →, \\rightleftharpoons for ⇌
- Charges: Fe^{3+}, OH^{-}
- State symbols: (aq), (s), (l), (g)
"""
    else:
        format_instruction = "Transcribe the handwritten text exactly as written."

    prompt = f"""
Transcribe the handwritten content in this image.

{format_instruction}

Respond ONLY with valid JSON:
{{
  "transcription": "the transcribed content",
  "format": "plain_text or latex",
  "confidence": 0.90,
  "illegible_sections": []
}}

If any sections are illegible, note them in illegible_sections as strings.
Return ONLY the JSON, no other text.
"""
    result = _call_gemini_vision(image_bytes, prompt)
    if not result or "error" in result:
        return {
            "transcription":    "[Transcription failed]",
            "format":           "plain_text",
            "confidence":       0.0,
            "illegible_sections": ["Full region unreadable"],
        }
    return result


# ── STEP 3B: Visual Evaluation (Path B — diagrams) ────────────────────────

def evaluate_visual_region(
    image_bytes:  bytes,
    region:       dict,
    question:     str  = "",
    subject:      str  = "",
    language:     str  = "english",
) -> dict:
    """
    Directly evaluate a visual region (diagram, structure, graph)
    without transcription. Gemini evaluates what it sees.
    """
    region_type = region.get("type", "diagram")
    description = region.get("description", "")

    # Build subject-specific evaluation guidance
    type_guidance = {
        "biology_diagram": """
Evaluate for:
- Correct anatomical structure and proportions
- Presence and accuracy of all required components
- Correct labeling of parts
- Directional accuracy (e.g. blood flow direction)
- Scientific accuracy of any annotations
List specifically what elements are present, missing, or incorrect.""",

        "chemical_structure": """
Evaluate for:
- Correct molecular structure
- Correct bond types and angles
- Correct stereochemistry if relevant
- Presence of lone pairs if required
- Correct formal charges
- For reactions: correct arrow pushing mechanism
Provide SMILES notation if the molecule is identifiable.""",

        "physics_diagram": """
Evaluate for:
- Correct representation of forces/fields/waves
- Accurate direction and magnitude indicators
- Correct labeling of components
- Proper use of conventions (e.g. dotted lines for field lines)
- Circuit completeness and correctness if applicable""",

        "graph_plot": """
Evaluate for:
- Correct axis labels and units
- Appropriate scale and range
- Correct shape/trend of the plotted data or function
- Presence of key features (intercepts, asymptotes, peaks)
- Accuracy of data points if plotting given data""",

        "engineering_diagram": """
Evaluate for:
- Correct use of standard symbols
- Logical flow and connectivity
- Completeness of the diagram
- Accuracy of labels and annotations""",
    }

    guidance = type_guidance.get(region_type, """
Evaluate the scientific accuracy and completeness of what is shown.
List what is present, what is missing, and what is incorrect.""")

    prompt = f"""
You are evaluating a student's handwritten STEM submission.

SUBJECT CONTEXT: {subject or "STEM"}
QUESTION: {question or "Evaluate this diagram/structure"}
CONTENT TYPE: {region_type}
WHAT I SEE: {description}

{guidance}

Evaluate this image and provide detailed feedback.

Respond ONLY with valid JSON:
{{
  "what_student_drew": "description of what is shown",
  "elements_present":   ["element1", "element2"],
  "elements_missing":   ["missing1", "missing2"],
  "elements_incorrect": ["incorrect1"],
  "smiles":             "SMILES notation if applicable, else null",
  "scientific_accuracy": "correct/partial/incorrect",
  "feedback_english":   "specific actionable feedback in English",
  "feedback_translated": "same feedback in {language} if not English, else null",
  "score":              0.75,
  "confidence":         0.85,
  "needs_review":       false
}}

Return ONLY the JSON, no other text.
"""
    result = _call_gemini_vision(image_bytes, prompt)
    if not result or "error" in result:
        return {
            "what_student_drew":  description,
            "elements_present":   [],
            "elements_missing":   [],
            "elements_incorrect": [],
            "smiles":             None,
            "scientific_accuracy": "unknown",
            "feedback_english":   "Could not evaluate this region automatically.",
            "feedback_translated": None,
            "score":              0.0,
            "confidence":         0.0,
            "needs_review":       True,
        }
    return result


# ── STEP 4: Generate text feedback (Path A) ────────────────────────────────

def generate_text_feedback(
    transcription: str,
    question:      str  = "",
    subject:       str  = "",
    language:      str  = "english",
) -> dict:
    """
    Generate feedback on transcribed text/equation content.
    Returns feedback in both English and detected language.
    """
    if not _gemini_available or not transcription:
        return {
            "feedback_english":    "Could not generate feedback.",
            "feedback_translated": None,
            "score":               0.0,
            "confidence":          0.0,
            "needs_review":        True,
        }

    try:
        prompt = f"""
You are evaluating a student's handwritten STEM submission.

SUBJECT: {subject or "STEM"}
QUESTION: {question or "Evaluate this answer"}
STUDENT ANSWER (transcribed from handwriting):
{transcription}

Evaluate the answer for correctness, completeness, and clarity.

Respond ONLY with valid JSON:
{{
  "feedback_english":    "specific actionable feedback in English",
  "feedback_translated": "same feedback in {language} if not English, else null",
  "score":               0.75,
  "confidence":          0.85,
  "is_correct":          "correct/partial/incorrect",
  "needs_review":        false
}}

Return ONLY the JSON, no other text.
"""
        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        text     = response.text.strip()
        if text.startswith("```"):
            text = re.sub(r"```(?:json)?", "", text).strip("` \n")
        return json.loads(text)

    except Exception as e:
        return {
            "feedback_english":    f"Feedback generation failed: {str(e)}",
            "feedback_translated": None,
            "score":               0.0,
            "confidence":          0.0,
            "needs_review":        True,
        }


# ── STEP 5: Build unified annotation ──────────────────────────────────────

def build_annotation(
    job_id:         str,
    page_num:       int,
    ann_index:      int,
    region:         dict,
    evaluation:     dict,
    transcription:  Optional[dict] = None,
    quality:        Optional[dict] = None,
) -> dict:
    """
    Convert OCR evaluation result into the standard annotation schema
    used by PDFViewer.jsx.
    """
    score      = float(evaluation.get("score", 0.0))
    confidence = float(evaluation.get("confidence", 0.0))

    # Build feedback text — combine English and translated
    feedback_en   = evaluation.get("feedback_english", "")
    feedback_tr   = evaluation.get("feedback_translated", "")
    feedback_text = feedback_en
    if feedback_tr and feedback_tr != feedback_en:
        feedback_text = f"{feedback_en}\n\n{feedback_tr}"

    # For visual regions — add elements present/missing
    elements_present   = evaluation.get("elements_present", [])
    elements_missing   = evaluation.get("elements_missing", [])
    elements_incorrect = evaluation.get("elements_incorrect", [])

    region_type = region.get("type", "text")

    # Map region type to display region type
    display_type_map = {
        "text":                 "paragraph",
        "math_equation":        "equation",
        "chemical_formula":     "equation",
        "chemical_structure":   "chemical_structure",
        "biology_diagram":      "biology_diagram",
        "physics_diagram":      "physics_diagram",
        "engineering_diagram":  "diagram",
        "graph_plot":           "diagram",
        "table":                "table",
    }

    return {
        "id":           f"ocr-{job_id[:8]}-p{page_num}-{ann_index:03d}",
        "page":         page_num,
        "bbox": {
            "x":      region.get("x_start", 0.05),
            "y":      region.get("y_start", 0.0),
            "width":  region.get("x_end", 0.95) - region.get("x_start", 0.05),
            "height": region.get("y_end", 1.0)  - region.get("y_start", 0.0),
        },
        "region_type":         display_type_map.get(region_type, "paragraph"),
        "feedback":            feedback_text,
        "score":               round(score, 3),
        "confidence":          round(confidence, 3),
        "needs_review":        evaluation.get("needs_review", confidence < 0.6),

        # Extra fields for diagram feedback cards
        "elements_present":    elements_present,
        "elements_missing":    elements_missing,
        "elements_incorrect":  elements_incorrect,
        "smiles":              evaluation.get("smiles"),
        "scientific_accuracy": evaluation.get("scientific_accuracy"),

        # Transcription data for text/equation regions
        "transcription":       transcription.get("transcription") if transcription else None,
        "transcription_format": transcription.get("format") if transcription else None,

        # Quality metadata
        "page_quality":        quality.get("quality_level", "clear") if quality else "clear",
    }


# ── MAIN PROCESS FUNCTION ──────────────────────────────────────────────────

def process(
    file_content:  bytes,
    job_id:        str,
    filename:      str,
    content_type:  str  = "",
    questions:     list = None,
    subject:       str  = "",
    language:      str  = "english",
) -> dict:
    """
    Main entry point for the OCR pipeline.

    Args:
        file_content : raw bytes (scanned PDF or phone photo)
        job_id       : unique job ID from app.py
        filename     : original filename
        content_type : MIME type
        questions    : list of question dicts [{q_id, number, text}]
        subject      : subject context for better evaluation
        language     : detected language for bilingual feedback

    Returns:
        dict matching diagrams_tables.py schema + OCR-specific fields
    """

    questions   = questions or []
    is_pdf      = (content_type or "").lower() == "application/pdf" \
                  or filename.lower().endswith(".pdf")

    pages_result      = []
    tables_result     = []
    figures_result    = []
    annotations       = []
    page_image_cache  = {}
    annotation_index  = 1
    page_quality_map  = {}

    suffix = ".pdf" if is_pdf else Path(filename).suffix or ".img"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = tmp.name
        tmp.write(file_content)

    try:
        # ── Get page images ───────────────────────────────────────────
        page_images_bytes = []

        if is_pdf:
            doc = fitz.open(tmp_path)
            for i in range(len(doc)):
                png = _page_to_png_bytes(doc[i], dpi=150)
                page_images_bytes.append(png)
                page_image_cache[str(i + 1)] = base64.b64encode(png).decode("ascii")
            doc.close()
        else:
            # Single image file (phone photo)
            png = _image_file_to_png_bytes(file_content, filename)
            page_images_bytes.append(png)
            page_image_cache["1"] = base64.b64encode(png).decode("ascii")

        total_pages = len(page_images_bytes)

        # ── Process each page ─────────────────────────────────────────
        for page_idx, page_png in enumerate(page_images_bytes):
            page_num = page_idx + 1

            # ── Quality check ─────────────────────────────────────────
            quality = detect_page_quality(page_png)
            page_quality_map[page_num] = quality
            quality_level = quality.get("quality_level", "clear")

            # Hard stop for completely unreadable pages
            if quality_level == "unreadable":
                pages_result.append({
                    "page_num":   page_num,
                    "text":       "[Page could not be processed — please upload a clearer scan]",
                    "words":      [],
                    "char_count": 0,
                    "quality":    quality_level,
                    "skipped":    True,
                })
                annotations.append({
                    "id":           f"ocr-{job_id[:8]}-p{page_num}-error",
                    "page":         page_num,
                    "bbox":         {"x": 0.05, "y": 0.05, "width": 0.9, "height": 0.9},
                    "region_type":  "error",
                    "feedback":     "⚠ Page could not be processed. Please re-upload a clearer scan of this page.",
                    "score":        0.0,
                    "confidence":   0.0,
                    "needs_review": True,
                })
                continue

            # ── Detect regions ────────────────────────────────────────
            regions = detect_regions(page_png)

            full_page_text = ""

            for region_idx, region in enumerate(regions):
                region_type    = region.get("type", "text")
                is_transcribable = region.get("transcribable", True)

                # Crop the region image for targeted evaluation
                # Use full page image for now — targeted crop can be added later
                region_image = page_png

                # ── Get matching question for this region ─────────────
                # Match question by index (best approximation without word-level alignment)
                q_index  = region_idx % len(questions) if questions else -1
                question = questions[q_index]["text"] if q_index >= 0 else ""

                if is_transcribable:
                    # ── PATH A: Transcribe then evaluate ─────────────
                    transcription = transcribe_region(region_image, region)
                    text_content  = transcription.get("transcription", "")
                    full_page_text += f"\n{text_content}"

                    evaluation = generate_text_feedback(
                        transcription = text_content,
                        question      = question,
                        subject       = subject,
                        language      = language,
                    )

                    ann = build_annotation(
                        job_id        = job_id,
                        page_num      = page_num,
                        ann_index     = annotation_index,
                        region        = region,
                        evaluation    = evaluation,
                        transcription = transcription,
                        quality       = quality,
                    )

                else:
                    # ── PATH B: Visual evaluation ─────────────────────
                    evaluation = evaluate_visual_region(
                        image_bytes = region_image,
                        region      = region,
                        question    = question,
                        subject     = subject,
                        language    = language,
                    )

                    ann = build_annotation(
                        job_id        = job_id,
                        page_num      = page_num,
                        ann_index     = annotation_index,
                        region        = region,
                        evaluation    = evaluation,
                        transcription = None,
                        quality       = quality,
                    )

                    # Add to figures for ParsedContent display
                    figures_result.append({
                        "id":               f"figure-p{page_num}-{region_idx + 1}",
                        "page_num":         page_num,
                        "type":             region_type,
                        "bbox": {
                            "x0": region.get("x_start", 0.05),
                            "y0": region.get("y_start", 0.0),
                            "x1": region.get("x_end",   0.95),
                            "y1": region.get("y_end",   1.0),
                        },
                        "width":            0,
                        "height":           0,
                        "source":           f"ocr_{region_type}",
                        "preview_data_url": _bytes_to_base64_url(region_image),
                        "description":      region.get("description", ""),
                        "elements_present":    evaluation.get("elements_present", []),
                        "elements_missing":    evaluation.get("elements_missing", []),
                        "elements_incorrect":  evaluation.get("elements_incorrect", []),
                        "smiles":              evaluation.get("smiles"),
                    })

                # Add quality warning to annotation if needed
                if quality_level in ("partial", "poor"):
                    ann["needs_review"] = True
                    ann["quality_warning"] = (
                        "Document quality is reduced — feedback accuracy may be affected"
                        if quality_level == "partial"
                        else "Document quality is poor — please re-upload a clearer scan"
                    )

                annotations.append(ann)
                annotation_index += 1

            pages_result.append({
                "page_num":   page_num,
                "text":       full_page_text.strip(),
                "words":      [],
                "char_count": len(full_page_text),
                "quality":    quality_level,
                "skipped":    False,
            })

        return {
            "job_id":            job_id,
            "status":            "done",
            "filename":          filename,
            "document_type":     "scanned_pdf" if is_pdf else "image",
            "page_count":        total_pages,
            "table_count":       len(tables_result),
            "figure_count":      len(figures_result),
            "pages":             pages_result,
            "tables":            tables_result,
            "figures":           figures_result,
            "annotations":       annotations,
            "page_image_cache":  page_image_cache,
            "page_quality_map":  page_quality_map,
            "ocr_pipeline":      True,
        }

    finally:
        Path(tmp_path).unlink(missing_ok=True)