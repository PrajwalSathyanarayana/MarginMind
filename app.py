from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import threading
from pathlib import Path
import fitz
import uuid
import os
import time
from Modal.text import process as process_text
from Modal.diagrams_tables import process as process_diagrams
from metrics_logger import log_evaluation
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store: {job_id: {...}}
job_store = {}


def _set_progress(job_id: str, percent: int, message: str):
    if job_id in job_store:
        job_store[job_id]["progress_percent"] = percent
        job_store[job_id]["progress_message"] = message


def _process_upload_background(
    job_id: str,
    content: bytes,
    filename: str,
    content_type: str,
):
    try:
        _set_progress(job_id, 10, "Analyzing document structure…")

        # Pass generate_feedback=False — skip Gemini annotations if OCR will run
        result = process_diagrams(
            content, job_id, filename, content_type or "",
            generate_feedback=False,
        )

        is_scanned = result.get("is_scanned", False)
        doc_type   = result.get("document_type", "pdf")

        if is_scanned or doc_type == "image":
            total_pages = result.get("page_count", "?")
            _set_progress(job_id, 20, f"Scanned document — starting OCR for {total_pages} pages…")

            try:
                from Modal.ocr import process as process_ocr

                def ocr_progress(pct: int, msg: str):
                    _set_progress(job_id, pct, msg)

                ocr_result = process_ocr(
                    file_content      = content,
                    job_id            = job_id,
                    filename          = filename,
                    content_type      = content_type or "",
                    progress_callback = ocr_progress,
                )
                # Keep page_image_cache from diagrams pipeline (already rendered)
                ocr_result["page_image_cache"] = result.get("page_image_cache", {})
                result = ocr_result
            except Exception as e:
                result["ocr_error"] = str(e)
                print(f"OCR pipeline failed, falling back: {e}")
        else:
            # Normal PDF — run Gemini annotation pass now
            _set_progress(job_id, 40, "Generating diagram and table feedback…")
            from Modal.diagrams_tables import _generate_gemini_feedback
            result["annotations"] = _generate_gemini_feedback(result, job_id)

        _set_progress(job_id, 88, "Detecting questions…")

        # Auto-detect questions in submission
        question_detection = {
            "has_questions": False, "confidence": 0.0,
            "verdict": "uncertain", "extracted_questions": [],
            "reasoning": "", "detected_question_count": 0,
        }

        if (content_type or "").lower() == "application/pdf" or \
                filename.lower().endswith(".pdf"):
            try:
                from Modal.text import detect_questions_in_submission
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                try:
                    question_detection = detect_questions_in_submission(tmp_path)
                    if (
                        question_detection.get("has_questions") and
                        len(question_detection.get("extracted_questions", [])) == 0
                    ):
                        question_detection["verdict"]       = "answers_only"
                        question_detection["has_questions"] = False
                        question_detection["reasoning"]     = (
                            question_detection.get("reasoning", "") +
                            " Questions detected but could not be extracted automatically — "
                            "please upload the question paper separately."
                        )
                finally:
                    os.unlink(tmp_path)
            except Exception as e:
                question_detection["reasoning"] = f"Detection error: {str(e)}"

        result["question_detection"] = question_detection
        result["status"]             = "done"
        result["progress_percent"]   = 100
        result["progress_message"]   = "Complete"
        job_store[job_id].update(result)

    except Exception as e:
        job_store[job_id]["status"]           = "error"
        job_store[job_id]["progress_percent"] = 0
        job_store[job_id]["progress_message"] = f"Error: {str(e)}"
        print(f"Background processing failed for {job_id}: {e}")


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    job_id  = str(uuid.uuid4())
    content = await file.read()

    # Seed job entry immediately so /status can respond right away
    job_store[job_id] = {
        "status":          "processing",
        "progress_percent": 0,
        "progress_message": "Queued…",
        "filename":        file.filename,
        "document_type":   "pdf",
        "page_count":      0,
        "table_count":     0,
        "figure_count":    0,
        "is_scanned":      False,
        "ocr_pipeline":    False,
        "detected_language": "english",
        "detected_script":   "latin",
    }

    # Start background thread — returns HTTP response immediately
    thread = threading.Thread(
        target=_process_upload_background,
        args=(job_id, content, file.filename, file.content_type or ""),
        daemon=True,
    )
    thread.start()

    return {
        "job_id":   job_id,
        "status":   "processing",
        "filename": file.filename,
    }


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in job_store:
        return {"job_id": job_id, "status": "not_found"}

    job = job_store[job_id]
    resp = {
        "job_id":           job_id,
        "status":           job["status"],
        "progress_percent": job.get("progress_percent", 0),
        "progress_message": job.get("progress_message", ""),
        "page_count":       job.get("page_count", 0),
    }

    # When done, include fields the frontend needs to proceed without a /feedback call
    if job["status"] == "done":
        resp.update({
            "filename":          job.get("filename", ""),
            "document_type":     job.get("document_type", "pdf"),
            "table_count":       job.get("table_count", 0),
            "figure_count":      job.get("figure_count", 0),
            "is_scanned":        job.get("is_scanned", False),
            "ocr_pipeline":      job.get("ocr_pipeline", False),
            "detected_language": job.get("detected_language", "english"),
            "detected_script":   job.get("detected_script", "latin"),
            "question_detection": job.get("question_detection", {}),
        })

    if job["status"] == "error":
        resp["error"] = job.get("progress_message", "Unknown error")

    return resp


@app.get("/feedback/{job_id}")
async def get_feedback(job_id: str):
    if job_id not in job_store:
        return {"error": "Job not found"}

    job = job_store[job_id]

    safe_tables = []
    for table in job.get("tables", []):
        safe_rows = [
            [cell if cell is not None else "" for cell in row]
            for row in table["data"]
        ]
        safe_tables.append({"page_num": table["page_num"], "data": safe_rows})

    return {
        "job_id":        job_id,
        "filename":      job["filename"],
        "document_type": job.get("document_type", "pdf"),
        "page_count":    job["page_count"],
        "tables":        safe_tables,
        "pages":         job.get("pages", []),
        "figures":       job.get("figures", []),
        "annotations":   job.get("annotations", []),
        "detected_language": job.get("detected_language", "english"),
        "detected_script":   job.get("detected_script", "latin"),
    }


@app.post("/text")
async def upload_text_qa(
    questionnaire: UploadFile = File(...),
    submission:    UploadFile = File(...),
):
    """Text-based Q&A evaluation endpoint."""
    t_upload_start = time.time()
    job_id = str(uuid.uuid4())

    questionnaire_content = await questionnaire.read()
    submission_content    = await submission.read()
    upload_read_s         = round(time.time() - t_upload_start, 3)

    result = process_text(
        questionnaire_content  = questionnaire_content,
        submission_content     = submission_content,
        job_id                 = job_id,
        questionnaire_filename = questionnaire.filename,
        submission_filename    = submission.filename,
    )

    # ── Persist metrics for poster graphs ────────────────────────────────
    evaluations = result.get("evaluations", [])
    confidence_scores = [
        f["confidence"]
        for e in evaluations
        for f in e.get("feedback", [])
        if isinstance(f.get("confidence"), (int, float))
    ]
    overall_scores = [
        e["overall_score"]
        for e in evaluations
        if isinstance(e.get("overall_score"), (int, float))
    ]

    timing = result.get("timing", {})
    timing["upload_read_s"] = upload_read_s
    timing.setdefault("total_s", round(
        upload_read_s + timing.get("extraction_s", 0) + timing.get("ai_evaluation_s", 0), 3
    ))

    log_evaluation({
        "job_id":           job_id,
        "question_count":   result.get("question_count", 0),
        "confidence_scores": confidence_scores,
        "overall_scores":   overall_scores,
        "timing":           timing,
    })
    # ─────────────────────────────────────────────────────────────────────

    job_store[job_id] = result
    return result


@app.get("/page/{job_id}/{page_num}")
async def get_page_image(job_id: str, page_num: int):
    """Returns a single PDF page rendered as a PNG image."""
    import base64

    if job_id not in job_store:
        return {"error": "Job not found"}

    job    = job_store[job_id]
    cached = job.get("page_image_cache", {}).get(str(page_num))
    if cached:
        from fastapi.responses import Response
        return Response(
            content=base64.b64decode(cached),
            media_type="image/png",
        )

    return {"error": "Page not available — re-upload document"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
