# MarginMind

> AI-powered margin feedback for student assignment submissions.  
> INFO 698 Capstone Project · University of Arizona · Spring 2026

---

## Overview

MarginMind is a hosted web application that accepts student assignment submissions and generates **anchored margin feedback** directly on the document. The system highlights specific regions (sentences, equations, diagrams, tables) and attaches contextual comments along with a structured review workflow — including confidence scores, "Needs Review" flags, and edit/resolve controls.

**Supported modalities**

| Modality | Description |
|---|---|
| Typed PDFs | Essays, reports, short-answer sets |
| Handwritten / Scanned STEM | Phone photos and CamScanner PDFs |
| Multilingual Assignments | English + additional languages; auto-detected |
| Mixed Layouts | Diagrams, tables, and text in the same document |

---

## Team

| Name | Modality (Primary) | Platform (Primary) |
|---|---|---|
| Prajwal Sathyanarayana | Diagrams / Tables | Backend |
| Vaishnav Mandlik | Handwritten / Scanned STEM | Frontend |
| Yash Salokhe | Typed Text | Evaluation / Quality |
| Kkshitij Kapadia | Multilingual | Hosting / Release |

**Project Mentor:** Rakshith Subramanyam (Axio Education)

---

## Architecture

```
Frontend (React + Vite)
    │
    ├── POST /upload          → returns job_id immediately (async)
    ├── GET  /status/{id}     → polls progress_percent + progress_message
    ├── GET  /feedback/{id}   → full annotations after status = "done"
    ├── POST /text            → Q&A evaluation (questionnaire + submission)
    └── GET  /page/{id}/{n}   → on-demand page image rendering

Backend (FastAPI)
    │
    ├── Modal/diagrams_tables.py   → PDF parsing, table/figure extraction, Gemini feedback
    ├── Modal/ocr.py               → Quality detection, region detection, transcription, feedback
    ├── Modal/text.py              → LangGraph Q&A evaluation pipeline
    └── app.py                     → FastAPI routes, background threading, job store
```

**Processing flow for scanned / handwritten PDFs:**

1. `POST /upload` returns `job_id` in ~100 ms and starts a background thread
2. `diagrams_tables.process(..., generate_feedback=False)` — renders pages, detects `is_scanned`
3. If scanned → `ocr.process(progress_callback=...)` runs page-by-page OCR (20–85%)
4. `detect_questions_in_submission()` — auto-detects if the doc contains questions (88%)
5. `status = "done"`, `progress_percent = 100`
6. Frontend polls `/status` every 2.5 s and reads live progress

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, CSS variables |
| Backend | FastAPI, Python 3.11, `threading` |
| AI / LLM | Google Gemini (via `google-genai` SDK) |
| Evaluation pipeline | LangChain + LangGraph |
| PDF processing | PyMuPDF (`fitz`), pdfplumber |
| OCR fallback | Tesseract (via `pytesseract`) |
| Environment | `python-dotenv`, `.env` file |

---

## Local Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Tesseract OCR installed and on `PATH` (optional — Gemini Vision is used as primary)

### Backend

```bash
# Create and activate virtual environment
python -m venv env
env\Scripts\activate          # Windows
# source env/bin/activate     # macOS/Linux

pip install -r requirements.txt

# Copy and fill in your keys
cp .env.example .env
```

**`.env` keys required:**

```
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash-preview-04-17
```

```bash
python app.py
# Server runs at http://127.0.0.1:8000
```

### Frontend

```bash
npm install
npm run dev
# UI runs at http://localhost:5173
```

---

## API Reference

### `POST /upload`
Upload a student submission PDF or image for background processing.

**Returns immediately:**
```json
{ "job_id": "uuid", "status": "processing", "filename": "..." }
```

### `GET /status/{job_id}`
Poll for processing progress.

```json
{
  "status": "processing | done | error",
  "progress_percent": 45,
  "progress_message": "OCR page 3/7…",
  "page_count": 7,
  "is_scanned": true,
  "ocr_pipeline": true,
  "question_detection": { ... }
}
```

### `GET /feedback/{job_id}`
Full annotation result once `status = "done"`.

```json
{
  "annotations": [ { "id", "page", "bbox", "feedback", "score", "confidence", "needs_review" } ],
  "pages": [...],
  "figures": [...],
  "tables": [...]
}
```

### `POST /text`
Q&A evaluation with a separate question paper.

- Form fields: `questionnaire` (PDF), `submission` (PDF)
- Returns full evaluation with per-question scores and bounding boxes

### `GET /page/{job_id}/{page_num}`
Returns a rendered page as a PNG image (served from in-memory cache).

---

## Project Milestones

| Milestone | Date | Description |
|---|---|---|
| Team Formation | 01/29/26 | Lanes defined, metrics established |
| Signed Proposal | 02/23/26 | Architecture finalized |
| M1: Foundation | 03/09/26 | Upload pipeline, basic extraction, UI display |
| M2: Logic / ML | 03/28/26 | Feedback engine, scoring metrics |
| M3: Modalities | 04/06/26 | Multi-modal routing >85% accuracy |
| M4: Deployment | 04/13/26 | Production-grade live app |
| M5: Polishing | 04/20/26 | Zero-error user flow, final report |
| Poster Demo | 04/23/26 | Live demo rehearsal |
| iShowcase | 05/01/26 | Final presentation, Student Union |

---

## Success Metrics

| Feature | Target |
|---|---|
| Upload-to-feedback completion rate | ≥ 95% |
| Async job failure rate | < 5% |
| Highlight position accuracy | ≥ 90% |
| Table extraction accuracy | ≥ 85% |
| Diagram detection precision | ≥ 80% |
| OCR text accuracy (clear images) | ≥ 90% |
| Language detection F1-score | ≥ 90% |
| Feedback semantic similarity (EN vs translated) | > 0.85 |
| False-critique rate | ≤ 15% |

---

## Repository Structure

```
MarginMind/
├── app.py                    # FastAPI application + background job runner
├── Modal/
│   ├── diagrams_tables.py    # Diagrams & tables modality
│   ├── ocr.py                # Handwritten/scanned STEM modality
│   └── text.py               # Typed text Q&A evaluation modality
├── src/
│   ├── App.jsx               # Main React application
│   ├── App.css               # Design token system + component styles
│   └── components/
│       ├── PDFViewer.jsx     # PDF renderer with annotation overlays
│       └── ParsedContent.jsx # Tables, figures, and parsed text display
├── .env                      # API keys (not committed)
├── requirements.txt
└── package.json
```

---

## License

Academic project — University of Arizona INFO 698 Capstone, Spring 2026.
