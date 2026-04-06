from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import tempfile
from pathlib import Path
import fitz
import uuid # henerate unique job ID 
from Modal.text import process as process_text
from Modal.diagrams_tables import process as process_diagrams
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temporary stand-in for Firestore (GCP keys coming in Milestone 2)
# Stores job results in memory while the server is running
job_store = {}


@app.get("/health") # Confirms server is alive and running
async def health_check():
    return {"status": "ok", "version": "1.0.0"}

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    job_id  = str(uuid.uuid4())
    content = await file.read()

    # Process with diagrams/tables modality
    result = process_diagrams(content, job_id, file.filename, file.content_type or "")
    job_store[job_id] = result

    # ── Auto-detect if submission contains questions ───────────────────
    # Runs on every PDF upload so frontend knows whether to ask
    # for a questionnaire or proceed directly to evaluation
    question_detection = {"has_questions": False, "confidence": 0.0,
                          "verdict": "uncertain", "extracted_questions": [],
                          "reasoning": "", "detected_question_count": 0}

    if (file.content_type or "").lower() == "application/pdf" or \
       file.filename.lower().endswith(".pdf"):
        try:
            import tempfile, os
            from Modal.text import detect_questions_in_submission
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                question_detection = detect_questions_in_submission(tmp_path)
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            question_detection["reasoning"] = f"Detection error: {str(e)}"

    # Store detection result alongside job
    job_store[job_id]["question_detection"] = question_detection

    return {
        "job_id":        job_id,
        "status":        "done",
        "filename":      file.filename,
        "document_type": result.get("document_type", "pdf"),
        "page_count":    result["page_count"],
        "table_count":   result["table_count"],
        "figure_count":  result.get("figure_count", 0),

        # Frontend uses these to decide next step
        "question_detection": question_detection,
    }

@app.get("/status/{job_id}") # Frontend polls this after upload to check if processing is complete
async def get_status(job_id: str):
    if job_id not in job_store:
        return {"job_id": job_id, "status": "not_found"}
    job = job_store[job_id]
    return {
        "job_id":     job_id,
        "status":     job["status"],
        "page_count": job.get("page_count", 0),
    }

@app.get("/feedback/{job_id}") # Returns full results for a completed job — frontend fetches this to display feedback
async def get_feedback(job_id: str):
    if job_id not in job_store:
        return {"error": "Job not found"}
    
    job = job_store[job_id]

    # Safely convert any None values in tables to empty string
    # pdfplumber sometimes returns None for empty table cells
    safe_tables = []
    for table in job.get("tables", []):
        safe_rows = [
            [cell if cell is not None else "" for cell in row]
            for row in table["data"]
        ]
        safe_tables.append({
            "page_num": table["page_num"],
            "data": safe_rows
        })

    return {
        "job_id":      job_id,
        "filename":    job["filename"],
        "document_type": job.get("document_type", "pdf"),
        "page_count":  job["page_count"],
        "tables":      safe_tables,
        "pages":       job.get("pages", []),
        "figures":     job.get("figures", []),
        "annotations": job.get("annotations", []),
    }

@app.post("/text")
async def upload_text_qa(
    questionnaire: UploadFile = File(...),
    submission: UploadFile = File(...)
):
    """
    Text-based Q&A evaluation endpoint.
    
    Expects:
    - questionnaire: PDF with questions
    - submission: PDF with student answers
    
    Returns:
    - Full evaluation results with feedback and bboxes
    """
    
    job_id = str(uuid.uuid4())
    
    # Read file contents
    questionnaire_content = await questionnaire.read()
    submission_content = await submission.read()
    
    # Process with text module
    result = process_text(
        questionnaire_content=questionnaire_content,
        submission_content=submission_content,
        job_id=job_id,
        questionnaire_filename=questionnaire.filename,
        submission_filename=submission.filename
    )
    
    # Store result
    job_store[job_id] = result
    
    # Return FULL result including evaluations
    return result




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)