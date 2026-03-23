// import { useState } from 'react'
// import './App.css'
// import ImageUpload from './components/ImageUpload'
// import UploadQuestions from './components/UploadQuestions'

// function App() {
//   const [image, setImage] = useState(null)
//   const [questionsFile, setQuestionsFile] = useState(null)
//   const [loading, setLoading] = useState(false)

//   const step = loading ? 3 : questionsFile ? 2 : image ? 2 : 1
//   const canGrade = image && questionsFile

//   const handleGrade = () => {
//     if (!canGrade) return
//     setLoading(true)
//   }

//   return (
//     <div className="app">
//       <header className="app-header">
//         <h1>Grader</h1>
//         <p>Upload assignment and questions to grade.</p>
//       </header>

//       <div className="steps">
//         {['Assignment', 'Questions', 'Grading'].map((label, i) => {
//           const n = i + 1
//           const cls = n < step ? 'completed' : n === step ? 'active' : ''
//           return (
//             <div key={label} className={`step ${cls}`}>
//               <span className="step-label">{label}</span>
//             </div>
//           )
//         })}
//       </div>

//       {loading ? (
//         <div className="section">
//           <div className="loading-wrap">
//             <div className="loader" />
//             <div className="loading-label">Analyzing assignment…</div>
//           </div>
//         </div>
//       ) : (
//         <>
//           <ImageUpload image={image} setImage={setImage} />
//           <UploadQuestions file={questionsFile} setFile={setQuestionsFile} />

//           <button
//             className="grade-btn"
//             disabled={!canGrade}
//             onClick={handleGrade}
//           >
//             {canGrade ? 'Grade Assignment' : 'Upload assignment & questions to grade'}
//           </button>
//         </>
//       )}
//     </div>
//   )
// }

// export default App

import { useEffect, useState } from "react";
import "./App.css";
import PDFUpload from "./components/ImageUpload";
import PDFViewer from "./components/PDFViewer";
import ParsedContent from "./components/ParsedContent";

function App() {
  // pdfFile     — the raw File object, used by PDFViewer to display the PDF
  // jobResult   — the response from backend: job_id, page_count, table_count
  // annotations — feedback items from /feedback endpoint
  const [pdfFile, setPdfFile] = useState(null);
  const [jobResult, setJobResult] = useState(null);
  const [annotations, setAnnotations] = useState([]);
  const [parsedContent, setParsedContent] = useState({
    pages: [],
    tables: [],
    figures: [],
  });
  const [loadingFeedback, setLoadingFeedback] = useState(false);
  const [imagePreviewUrl, setImagePreviewUrl] = useState(null);

  // Called by PDFUpload when backend /upload responds successfully
  const handleUploadComplete = async (file, result) => {
    setPdfFile(file);
    setJobResult(result);

    // Fetch the full feedback using the job_id returned from /upload
    try {
      setLoadingFeedback(true);
      const response = await fetch(
        `http://127.0.0.1:8000/feedback/${result.job_id}`,
      );
      const feedbackData = await response.json();
      setAnnotations(feedbackData.annotations || []);
      setParsedContent({
        pages: feedbackData.pages || [],
        tables: feedbackData.tables || [],
        figures: feedbackData.figures || [],
      });
    } catch (err) {
      console.error("Failed to fetch feedback:", err);
      setAnnotations([]);
      setParsedContent({ pages: [], tables: [], figures: [] });
    } finally {
      setLoadingFeedback(false);
    }
  };

  // Reset everything back to upload screen
  const handleReset = () => {
    setPdfFile(null);
    setJobResult(null);
    setAnnotations([]);
    setParsedContent({ pages: [], tables: [], figures: [] });
  };

  const isPdfUpload = pdfFile?.type === "application/pdf";

  useEffect(() => {
    if (!pdfFile || isPdfUpload) {
      setImagePreviewUrl(null);
      return;
    }

    const url = URL.createObjectURL(pdfFile);
    setImagePreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [pdfFile, isPdfUpload]);

  return (
    <div className="app">
      {/* ── HEADER ────────────────────────────────────────────── */}
      <header className="app-header">
        <h1>MarginMind</h1>
        {/* <p>Upload a student assignment to get anchored feedback.</p> */}
      </header>

      {/* ── UPLOAD SCREEN ─────────────────────────────────────── */}
      {!pdfFile && <PDFUpload onUploadComplete={handleUploadComplete} />}

      {/* ── LOADING FEEDBACK ──────────────────────────────────── */}
      {pdfFile && loadingFeedback && (
        <div className="section">
          <div className="loading-wrap">
            <div className="loader" />
            <div className="loading-label">Loading feedback…</div>
          </div>
        </div>
      )}

      {/* ── PDF VIEWER + MARGIN FEEDBACK ──────────────────────── */}
      {pdfFile && !loadingFeedback && (
        <>
          {/* Info bar showing upload result */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "10px 16px",
              background: "#f0efe9",
              border: "1px solid #e0ddd6",
              borderRadius: "8px",
              marginTop: "16px",
            }}
          >
            <div style={{ fontSize: "0.85rem", color: "#3d3b30" }}>
              <strong>{jobResult?.filename}</strong>
              <span style={{ color: "#9a9888", marginLeft: "12px" }}>
                {jobResult?.page_count} page
                {jobResult?.page_count !== 1 ? "s" : ""}
                {jobResult?.table_count > 0 &&
                  ` · ${jobResult.table_count} table${jobResult.table_count !== 1 ? "s" : ""} detected`}
                {jobResult?.figure_count > 0 &&
                  ` · ${jobResult.figure_count} figure${jobResult.figure_count !== 1 ? "s" : ""} detected`}
              </span>
            </div>
            <button
              onClick={handleReset}
              style={{
                background: "none",
                border: "1px solid #d0cec6",
                borderRadius: "6px",
                padding: "5px 12px",
                fontSize: "0.8rem",
                cursor: "pointer",
                color: "#6b6960",
              }}
            >
              ← Upload Another
            </button>
          </div>

          {/* PDF viewer with left margin panel */}
          {isPdfUpload ? (
            <PDFViewer pdfFile={pdfFile} annotations={annotations} />
          ) : (
            <div className="section image-preview-section">
              <div className="section-header">
                <h2 className="section-title">Image Preview</h2>
                <p className="section-desc">
                  Uploaded image used for parsing pipeline
                </p>
              </div>
              <img
                src={imagePreviewUrl || ""}
                alt="Uploaded document"
                className="uploaded-image-preview"
              />
            </div>
          )}

          <ParsedContent parsed={parsedContent} />
        </>
      )}
    </div>
  );
}

export default App;
