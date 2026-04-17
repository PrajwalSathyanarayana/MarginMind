import tempfile
import io
import base64
from shutil import which
from pathlib import Path
import fitz
import pdfplumber
import os
import re
import json
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

try:
    import numpy as np
except ImportError:
    np = None

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from PIL import Image
except ImportError:
    Image = None


TESSERACT_AVAILABLE = bool(pytesseract and Image and which("tesseract"))

if pytesseract and Image and not TESSERACT_AVAILABLE:
    # Fallback for shells where Homebrew path is not exported.
    for candidate in ("/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"):
        if Path(candidate).exists():
            pytesseract.pytesseract.tesseract_cmd = candidate
            TESSERACT_AVAILABLE = True
            break


def _safe_ocr_text_from_bytes(image_bytes: bytes) -> str:
    if not TESSERACT_AVAILABLE:
        return ""
    try:
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return pytesseract.image_to_string(pil_image) or ""
    except Exception:
        return ""


def _decode_image_to_bgr(image_bytes: bytes):
    if not np:
        return None, 0, 0

    # Fast path for common formats supported by OpenCV.
    if cv2:
        np_img = np.frombuffer(image_bytes, dtype=np.uint8)
        decoded = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        if decoded is not None:
            h, w = decoded.shape[:2]
            return decoded, w, h

    # Fallback path for formats OpenCV may not decode well on macOS (e.g., HEIC).
    if Image:
        try:
            pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            rgb = np.array(pil_image)
            if cv2:
                bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            else:
                bgr = rgb
            h, w = bgr.shape[:2]
            return bgr, w, h
        except Exception:
            return None, 0, 0

    return None, 0, 0


def _pixmap_png_bytes(page: fitz.Page, zoom: float = 2.0) -> bytes:
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix)
    return pix.tobytes("png")


def _safe_ocr_text_from_pdf_page(page: fitz.Page) -> str:
    return _safe_ocr_text_from_bytes(_pixmap_png_bytes(page))


def _bytes_to_data_url(image_bytes: bytes, mime: str = "image/png") -> str:
    if not image_bytes:
        return ""
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _normalize_bbox(bbox, width: float, height: float) -> dict:
    x0, y0, x1, y1 = bbox
    w = max(1.0, width)
    h = max(1.0, height)
    return {
        "x0": round(max(0.0, x0) / w, 4),
        "y0": round(max(0.0, y0) / h, 4),
        "x1": round(min(w, x1) / w, 4),
        "y1": round(min(h, y1) / h, 4),
    }


def _bbox_iou(a, b) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b

    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)

    iw = max(0, ix1 - ix0)
    ih = max(0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0

    a_area = max(1, ax1 - ax0) * max(1, ay1 - ay0)
    b_area = max(1, bx1 - bx0) * max(1, by1 - by0)
    union = a_area + b_area - inter
    return inter / union if union > 0 else 0.0


def _nms_rects(rects, iou_threshold: float = 0.5):
    kept = []
    for rect in rects:
        if any(_bbox_iou(rect, existing) >= iou_threshold for existing in kept):
            continue
        kept.append(rect)
    return kept


def _image_to_ocr_boxes(image) -> list:
    if not TESSERACT_AVAILABLE or image is None:
        return []
    try:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if cv2 else image
        data = pytesseract.image_to_data(
            rgb,
            output_type=pytesseract.Output.DICT,
            config="--oem 3 --psm 6",
        )
    except Exception:
        return []

    boxes = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        try:
            conf = float(data.get("conf", ["-1"])[i])
        except Exception:
            conf = -1.0
        if not text or conf < 35:
            continue
        x, y = int(data["left"][i]), int(data["top"][i])
        w, h = int(data["width"][i]), int(data["height"][i])
        if w < 3 or h < 3:
            continue
        boxes.append((x, y, x + w, y + h))
    return boxes


def _extract_figures_from_pdf_page(page: fitz.Page, page_num: int) -> list:
    figures = []
    raw = page.get_text("rawdict")
    page_width = float(page.rect.width)
    page_height = float(page.rect.height)

    for idx, block in enumerate(raw.get("blocks", [])):
        if block.get("type") != 1:
            continue
        bbox = block.get("bbox")
        if not bbox or len(bbox) != 4:
            continue

        x0, y0, x1, y1 = bbox
        bw = max(0.0, x1 - x0)
        bh = max(0.0, y1 - y0)
        area = bw * bh

        # Skip very tiny embedded images (icons/noise).
        if area < 2_500:
            continue

        figures.append({
            "id": f"figure-p{page_num}-{idx + 1}",
            "page_num": page_num,
            "type": "figure",
            "bbox": _normalize_bbox((x0, y0, x1, y1), page_width, page_height),
            "width": int(round(bw)),
            "height": int(round(bh)),
            "source": "pdf_embedded_image",
            "preview_data_url": "",
        })

    # Generate lightweight preview images from the detected figure bbox.
    for figure in figures:
        bbox = figure.get("bbox", {})
        clip = fitz.Rect(
            float(bbox.get("x0", 0.0)) * page_width,
            float(bbox.get("y0", 0.0)) * page_height,
            float(bbox.get("x1", 1.0)) * page_width,
            float(bbox.get("y1", 1.0)) * page_height,
        )
        if clip.width < 2 or clip.height < 2:
            continue
        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), clip=clip, alpha=False)
            figure["preview_data_url"] = _bytes_to_data_url(pix.tobytes("png"), "image/png")
        except Exception:
            figure["preview_data_url"] = ""

    return figures


def _extract_tables_from_image_bytes(image_bytes: bytes) -> list:
    if not cv2 or not np:
        return []

    image, w, h = _decode_image_to_bgr(image_bytes)
    if image is None:
        return []

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    bw = cv2.adaptiveThreshold(
        ~gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        15,
        -10,
    )

    h, w = gray.shape
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, w // 30), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, h // 30)))

    horizontal = cv2.morphologyEx(bw, cv2.MORPH_OPEN, horizontal_kernel)
    vertical = cv2.morphologyEx(bw, cv2.MORPH_OPEN, vertical_kernel)
    table_mask = cv2.add(horizontal, vertical)

    contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidate_rects = []
    image_area = max(1, w * h)

    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        area = cw * ch
        if cw < 120 or ch < 60:
            continue
        if area / image_area > 0.75:
            continue
        if x <= 3 and y <= 3 and (x + cw) >= (w - 3) and (y + ch) >= (h - 3):
            continue
        candidate_rects.append((x, y, x + cw, y + ch))

    candidate_rects.sort(key=lambda r: (r[2] - r[0]) * (r[3] - r[1]), reverse=True)
    rects = _nms_rects(candidate_rects, iou_threshold=0.5)
    tables = []

    for idx, rect in enumerate(rects, start=1):
        x, y, x1, y1 = rect
        cw = x1 - x
        ch = y1 - y
        crop = image[y:y + ch, x:x + cw]
        table_text = ""
        if TESSERACT_AVAILABLE:
            try:
                table_text = pytesseract.image_to_string(crop)
            except Exception:
                table_text = ""

        rows = []
        for line in (table_text or "").splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            cells = [cell for cell in cleaned.replace("\t", "  ").split("  ") if cell.strip()]
            rows.append(cells if cells else [cleaned])

        joined = " ".join(" ".join(row) for row in rows).strip()
        alpha_num_count = sum(ch.isalnum() for ch in joined)
        if TESSERACT_AVAILABLE and alpha_num_count < 8:
            continue

        if TESSERACT_AVAILABLE and len(rows) < 2:
            continue

        tables.append({
            "page_num": 1,
            "data": rows if rows else [["Detected table region"]],
            "bbox": {
                "x0": round(x / max(1, w), 4),
                "y0": round(y / max(1, h), 4),
                "x1": round((x + cw) / max(1, w), 4),
                "y1": round((y + ch) / max(1, h), 4),
            },
        })

    if not tables and not TESSERACT_AVAILABLE:
        for rect in rects[:3]:
            x, y, x1, y1 = rect
            tables.append({
                "page_num": 1,
                "data": [["Detected table region (OCR unavailable)"]],
                "bbox": {
                    "x0": round(x / max(1, w), 4),
                    "y0": round(y / max(1, h), 4),
                    "x1": round(x1 / max(1, w), 4),
                    "y1": round(y1 / max(1, h), 4),
                },
            })

    return tables


def _extract_figures_from_image_bytes(image_bytes: bytes) -> list:
    if not cv2 or not np:
        return []

    image, w, h = _decode_image_to_bgr(image_bytes)
    if image is None:
        return []

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    image_area = max(1, w * h)

    bw = cv2.adaptiveThreshold(
        ~gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        15,
        -10,
    )
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, w // 30), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, h // 30)))
    horizontal = cv2.morphologyEx(bw, cv2.MORPH_OPEN, horizontal_kernel)
    vertical = cv2.morphologyEx(bw, cv2.MORPH_OPEN, vertical_kernel)
    table_mask = cv2.add(horizontal, vertical)
    non_table = cv2.bitwise_and(gray, gray, mask=cv2.bitwise_not(table_mask))

    edges = cv2.Canny(non_table, 60, 180)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape
    figures = []
    candidate_rects = []

    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        area = cw * ch
        area_ratio = area / image_area
        if area < 20_000:
            continue
        if cw < 120 or ch < 120:
            continue
        if area_ratio < 0.015:
            continue
        if area_ratio > 0.70:
            continue
        if x <= 3 and y <= 3 and (x + cw) >= (w - 3) and (y + ch) >= (h - 3):
            continue
        aspect = cw / max(1.0, ch)
        if aspect < 0.25 or aspect > 4.2:
            continue
        candidate_rects.append((x, y, x + cw, y + ch))

    candidate_rects.sort(key=lambda r: (r[2] - r[0]) * (r[3] - r[1]), reverse=True)
    rects = _nms_rects(candidate_rects, iou_threshold=0.4)

    for rect in rects[:6]:
        x, y, x1, y1 = rect
        cw = x1 - x
        ch = y1 - y

        figures.append({
            "id": "",
            "page_num": 1,
            "type": "figure",
            "bbox": {
                "x0": round(x / max(1, w), 4),
                "y0": round(y / max(1, h), 4),
                "x1": round((x + cw) / max(1, w), 4),
                "y1": round((y + ch) / max(1, h), 4),
            },
            "width": cw,
            "height": ch,
            "source": "image_region",
            "preview_data_url": "",
        })

    top_figures = figures

    for seq, figure in enumerate(top_figures, start=1):
        figure["id"] = f"figure-p1-{seq}"
        bbox = figure.get("bbox", {})
        x0 = int(round(float(bbox.get("x0", 0.0)) * w))
        y0 = int(round(float(bbox.get("y0", 0.0)) * h))
        x1 = int(round(float(bbox.get("x1", 1.0)) * w))
        y1 = int(round(float(bbox.get("y1", 1.0)) * h))
        crop = image[max(0, y0):min(h, y1), max(0, x0):min(w, x1)]
        if crop.size == 0:
            continue
        try:
            ok, encoded = cv2.imencode(".png", crop)
            if ok:
                figure["preview_data_url"] = _bytes_to_data_url(encoded.tobytes(), "image/png")
        except Exception:
            figure["preview_data_url"] = ""

    return top_figures


def _process_pdf(file_content: bytes, job_id: str, filename: str, temp_path: str) -> dict:
    pages = []
    tables = []
    page_images = []
    figures = []

    with pdfplumber.open(temp_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            text = page.extract_text() or ""
            words = [
                {
                    "text": w["text"],
                    "x0": round(w["x0"] / page.width, 4),
                    "y0": round(w["top"] / page.height, 4),
                    "x1": round(w["x1"] / page.width, 4),
                    "y1": round(w["bottom"] / page.height, 4),
                }
                for w in page.extract_words()
            ]

            pages.append({
                "page_num": page_num,
                "text": text,
                "words": words,
                "char_count": len(text),
            })

            raw_tables = page.extract_tables() or []
            for table in raw_tables:
                tables.append({
                    "page_num": page_num,
                    "data": table,
                })

    doc = fitz.open(temp_path)
    page_image_cache = {}  # stores base64 PNG per page
    try:
        for i in range(len(doc)):
            page_num = i + 1
            page     = doc[i]

            # Render at 150dpi — good balance of quality vs size
            matrix = fitz.Matrix(150/72, 150/72)
            pix    = page.get_pixmap(matrix=matrix, alpha=False)
            png_bytes = pix.tobytes("png")

            # Cache as base64 for the /page endpoint
            page_image_cache[str(page_num)] = base64.b64encode(png_bytes).decode("ascii")

            page_images.append({
                "page_num": page_num,
                "width":    pix.width,
                "height":   pix.height,
            })
    finally:
        doc.close()

    return {
        "job_id": job_id,
        "status": "done",
        "filename": filename,
        "document_type": "pdf",
        "page_count": len(pages),
        "table_count": len(tables),
        "figure_count": len(figures),
        "pages": pages,
        "tables": tables,
        "figures": figures,
        "page_images": page_images,
        "page_image_cache": page_image_cache,
    }


def _process_image(file_content: bytes, job_id: str, filename: str) -> dict:
    text = _safe_ocr_text_from_bytes(file_content)
    tables = _extract_tables_from_image_bytes(file_content)
    figures = _extract_figures_from_image_bytes(file_content)

    if not text and not TESSERACT_AVAILABLE:
        text = (
            "OCR text unavailable: system Tesseract is not installed. "
            "Install it with: brew install tesseract"
        )

    if Image:
        try:
            with Image.open(io.BytesIO(file_content)) as img:
                width, height = img.size
        except Exception:
            width, height = 0, 0
    else:
        width, height = 0, 0

    pages = [{
        "page_num": 1,
        "text": text,
        "words": [],
        "char_count": len(text),
    }]

    return {
        "job_id": job_id,
        "status": "done",
        "filename": filename,
        "document_type": "image",
        "page_count": 1,
        "table_count": len(tables),
        "figure_count": len(figures),
        "pages": pages,
        "tables": tables,
        "figures": figures,
        "page_images": [{"page_num": 1, "width": width, "height": height}],
    }

def _generate_gemini_feedback(result: dict, job_id: str) -> list:
    """
    Generates real feedback annotations using Gemini.
    Analyzes extracted text, tables, and figures from the document.
    Returns a list of annotations in the same schema as mock_annotations.
    Falls back to mock annotations if Gemini is unavailable.
    """

    # ── Fallback if no API key ─────────────────────────────────────────
    if not GEMINI_API_KEY:
        return [
            {
                "id":           f"annotation-{job_id[:8]}-001",
                "page":         1,
                "bbox":         {"x": 0.1, "y": 0.2, "width": 0.8, "height": 0.05},
                "region_type":  "paragraph",
                "feedback":     "Gemini API key not configured. Add GEMINI_API_KEY to .env",
                "confidence":   0.0,
                "needs_review": True,
            }
        ]

    try:
        model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")
        annotations = []
        annotation_index = 1

        # ── Analyze text regions per page ─────────────────────────────
        for page in result.get("pages", []):
            page_num  = page.get("page_num", 1)
            page_text = page.get("text", "").strip()

            if not page_text or len(page_text) < 30:
                continue

            text_prompt = f"""
You are an academic grader reviewing a student assignment submission.

PAGE {page_num} TEXT:
{page_text[:3000]}

Analyze this student submission text and provide specific, constructive feedback.
Identify regions that are partially correct, incorrect, or need improvement.

Respond ONLY with a valid JSON array. Each object must follow this exact schema:
[
  {{
    "region_type": "paragraph",
    "feedback": "specific constructive feedback about this region",
    "highlight_phrase": "exact short phrase from the text to highlight (max 8 words)",
    "confidence": 0.85,
    "needs_review": false,
    "bbox_hint": "top|middle|bottom"
  }}
]

Rules:
- Return 1 to 3 feedback items per page
- highlight_phrase must be exact text from the submission
- confidence is 0.0 to 1.0 (how sure you are about the feedback)
- needs_review is true if confidence < 0.6
- bbox_hint indicates where on the page the phrase appears
- Return ONLY the JSON array, no markdown, no explanation
"""

            try:
                response      = model.generate_content(text_prompt)
                response_text = response.text.strip()

                # Strip markdown code fences if present
                if response_text.startswith("```"):
                    response_text = re.sub(r"```(?:json)?", "", response_text).strip("` \n")

                items = json.loads(response_text)
                if not isinstance(items, list):
                    items = [items]

                for item in items:
                    # Map bbox_hint to approximate normalized coordinates
                    hint_map = {
                        "top":    {"x": 0.05, "y": 0.05, "width": 0.9, "height": 0.08},
                        "middle": {"x": 0.05, "y": 0.40, "width": 0.9, "height": 0.08},
                        "bottom": {"x": 0.05, "y": 0.75, "width": 0.9, "height": 0.08},
                    }
                    bbox = hint_map.get(
                        item.get("bbox_hint", "middle"),
                        {"x": 0.05, "y": 0.40, "width": 0.9, "height": 0.08}
                    )

                    # Try to find exact phrase in words for precise bbox
                    phrase = item.get("highlight_phrase", "")
                    if phrase:
                        words = page.get("words", [])
                        phrase_lower  = phrase.lower().split()
                        phrase_length = len(phrase_lower)

                        for wi in range(len(words) - phrase_length + 1):
                            window = words[wi:wi + phrase_length]
                            if [w["text"].lower() for w in window] == phrase_lower:
                                bbox = {
                                    "x":      min(w["x0"] for w in window),
                                    "y":      min(w["y0"] for w in window),
                                    "width":  max(w["x1"] for w in window) - min(w["x0"] for w in window),
                                    "height": max(w["y1"] for w in window) - min(w["y0"] for w in window),
                                }
                                break

                    confidence = float(item.get("confidence", 0.75))

                    annotations.append({
                        "id":           f"annotation-{job_id[:8]}-{annotation_index:03d}",
                        "page":         page_num,
                        "bbox":         bbox,
                        "region_type":  item.get("region_type", "paragraph"),
                        "feedback":     item.get("feedback", ""),
                        "confidence":   confidence,
                        "needs_review": confidence < 0.6 or item.get("needs_review", False),
                    })
                    annotation_index += 1

            except Exception:
                # If Gemini fails for this page, skip it silently
                continue

        # ── Analyze tables ─────────────────────────────────────────────
        for table in result.get("tables", []):
            page_num = table.get("page_num", 1)
            data     = table.get("data", [])

            if not data or len(data) < 2:
                continue

            # Format table as readable text for Gemini
            table_text = "\n".join(
                " | ".join(str(cell) if cell else "" for cell in row)
                for row in data
            )

            table_prompt = f"""
You are an academic grader reviewing a student assignment.

A TABLE was detected on page {page_num}:
{table_text[:1000]}

Evaluate this table and provide specific feedback.

Respond ONLY with a valid JSON object:
{{
  "feedback": "specific feedback about the table structure and content",
  "confidence": 0.80,
  "needs_review": false
}}

Return ONLY the JSON object, no markdown.
"""

            try:
                response      = model.generate_content(table_prompt)
                response_text = response.text.strip()

                if response_text.startswith("```"):
                    response_text = re.sub(r"```(?:json)?", "", response_text).strip("` \n")

                item       = json.loads(response_text)
                confidence = float(item.get("confidence", 0.75))

                annotations.append({
                    "id":           f"annotation-{job_id[:8]}-{annotation_index:03d}",
                    "page":         page_num,
                    "bbox":         {"x": 0.05, "y": 0.3, "width": 0.9, "height": 0.3},
                    "region_type":  "table",
                    "feedback":     item.get("feedback", ""),
                    "confidence":   confidence,
                    "needs_review": confidence < 0.6 or item.get("needs_review", False),
                })
                annotation_index += 1

            except Exception:
                continue

        # ── Analyze figures ────────────────────────────────────────────
        for figure in result.get("figures", []):
            page_num      = figure.get("page_num", 1)
            preview_url   = figure.get("preview_data_url", "")
            figure_source = figure.get("source", "unknown")

            if not preview_url:
                continue

            try:
                # Decode base64 image and send to Gemini Vision
                header, b64_data = preview_url.split(",", 1)
                img_bytes        = base64.b64decode(b64_data)

                image_part = {"mime_type": "image/png", "data": img_bytes}

                figure_prompt = f"""
You are an academic grader reviewing a diagram/figure from a student assignment.
This figure was detected on page {page_num} (source: {figure_source}).

Evaluate this diagram and provide specific feedback on:
- Accuracy and correctness
- Labeling and annotations
- Clarity and presentation
- Completeness

Respond ONLY with a valid JSON object:
{{
  "feedback": "specific feedback about the diagram",
  "confidence": 0.80,
  "needs_review": false,
  "region_type": "diagram"
}}

Return ONLY the JSON object, no markdown.
"""

                response      = model.generate_content([image_part, figure_prompt])
                response_text = response.text.strip()

                if response_text.startswith("```"):
                    response_text = re.sub(r"```(?:json)?", "", response_text).strip("` \n")

                item       = json.loads(response_text)
                confidence = float(item.get("confidence", 0.75))
                fig_bbox   = figure.get("bbox", {})

                annotations.append({
                    "id":           f"annotation-{job_id[:8]}-{annotation_index:03d}",
                    "page":         page_num,
                    "bbox":         {
                        "x":      fig_bbox.get("x0", 0.1),
                        "y":      fig_bbox.get("y0", 0.1),
                        "width":  fig_bbox.get("x1", 0.9) - fig_bbox.get("x0", 0.1),
                        "height": fig_bbox.get("y1", 0.9) - fig_bbox.get("y0", 0.1),
                    },
                    "region_type":  item.get("region_type", "diagram"),
                    "feedback":     item.get("feedback", ""),
                    "confidence":   confidence,
                    "needs_review": confidence < 0.6 or item.get("needs_review", False),
                })
                annotation_index += 1

            except Exception:
                continue

        # ── If nothing was generated, return a fallback ────────────────
        if not annotations:
            annotations.append({
                "id":           f"annotation-{job_id[:8]}-001",
                "page":         1,
                "bbox":         {"x": 0.05, "y": 0.05, "width": 0.9, "height": 0.08},
                "region_type":  "paragraph",
                "feedback":     "No specific issues detected. Document processed successfully.",
                "confidence":   0.70,
                "needs_review": False,
            })

        return annotations

    except Exception as e:
        # Full fallback if anything catastrophic happens
        return [
            {
                "id":           f"annotation-{job_id[:8]}-001",
                "page":         1,
                "bbox":         {"x": 0.05, "y": 0.05, "width": 0.9, "height": 0.08},
                "region_type":  "paragraph",
                "feedback":     f"Feedback generation encountered an error: {str(e)}",
                "confidence":   0.0,
                "needs_review": True,
            }
        ]
    
def process(file_content: bytes, job_id: str, filename: str, content_type: str = "") -> dict:
    """
    Main entry point for the Diagrams/Tables modality.
    Called by app.py when a document is uploaded.

    Args:
        file_content : raw bytes of the uploaded PDF
        job_id       : unique ID generated by app.py for this job
        filename     : original filename of the uploaded PDF

    Returns:
        dict with pages, tables, page_images, and mock annotations
    """

    is_pdf = (content_type or "").lower() == "application/pdf" or filename.lower().endswith(".pdf")

    suffix = ".pdf" if is_pdf else Path(filename).suffix or ".img"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        temp_path = temp.name
        temp.write(file_content)

    try:
        if is_pdf:
            result = _process_pdf(file_content, job_id, filename, temp_path)
        else:
            result = _process_image(file_content, job_id, filename)

        # Mock annotations (placeholder for scoring model output).
        # Placeholder for real Gemini feedback — arrives in Milestone 2
        # Schema is identical to what the real Gemini service will return
        # so the frontend can be built against this now without waiting for keys
        mock_annotations = [
            {
                "id":           f"annotation-{job_id[:8]}-001",
                "page":         1,
                "bbox":         {
                    "x":      0.1,
                    "y":      0.2,
                    "width":  0.8,
                    "height": 0.05
                },
                "region_type":  "paragraph",
                "feedback":     "Good structure, but the argument needs more supporting evidence.",
                "confidence":   0.87,
                "needs_review": False,
            }
        ]

        result["annotations"] = _generate_gemini_feedback(result, job_id)
        return result

    finally:
        # Always delete the temp file even if something crashes above
        Path(temp_path).unlink(missing_ok=True)