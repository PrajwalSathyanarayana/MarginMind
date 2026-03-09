from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import tempfile
from pathlib import Path
import fitz
import uuid # henerate unique job ID 

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

    job_id = str(uuid.uuid4())

    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp:
        temp_path = temp.name
        content = await file.read()
        temp.write(content)
    
    try:
        doc = fitz.open(temp_path)
        text = ""
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text += f"\n--- PAGE {page_num + 1} ---\n"
            text += page.get_text()
        page_count = len(doc)
        doc.close()
        
        # Save result to job store so /status and /feedback can retrieve it
        job_store[job_id] = {
            "job_id":     job_id,
            "status":     "done",
            "filename":   file.filename,
            "page_count": page_count,
            "content":    text,
            "annotations": [],  # will be filled by modality processors in M2
        }
        
        return {
            "job_id":   job_id,       # added — frontend uses this to poll status
            "filename": file.filename,
            "pages":    page_count,
            "content":  text
        }
    
    finally:
        Path(temp_path).unlink()

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
    return {
        "job_id":      job_id,
        "filename":    job["filename"],
        "page_count":  job["page_count"],
        "content":     job["content"],
        "annotations": job["annotations"],
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)