import { useState } from "react";
import "./App.css";
import PDFViewer from "./components/PDFViewer";
import ParsedContent from "./components/ParsedContent";

// ── Icons ──────────────────────────────────────────────────────────────────
function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}

// QA evaluation steps for the loading checklist
const QA_STEPS = [
  { label: "Uploading student submission", doneAt: 12 },
  { label: "Analyzing document structure", doneAt: 55 },
  { label: "Running OCR / Q&A evaluation", doneAt: 88 },
  { label: "Processing results",           doneAt: 98 },
];

// ── File drop zone component ───────────────────────────────────────────────
function FileDropZone({ label, desc, file, onFile, accept = "application/pdf" }) {
  const [dragover, setDragover] = useState(false);
  const ref = { current: null };

  const handleFile = (f) => { if (!f) return; onFile(f); };

  return (
    <div className="upload-zone-wrap">
      <div className="upload-zone-field-label">{label}</div>
      <div className="upload-zone-field-desc">{desc}</div>
      <input
        ref={(el) => (ref.current = el)}
        type="file"
        accept={accept}
        style={{ display: "none" }}
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      {!file ? (
        <div
          className={`upload-zone${dragover ? " dragover" : ""}`}
          onClick={() => ref.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragover(true); }}
          onDragLeave={() => setDragover(false)}
          onDrop={(e) => { e.preventDefault(); setDragover(false); handleFile(e.dataTransfer.files?.[0]); }}
        >
          <div className="upload-icon-wrap">
            <UploadIcon />
          </div>
          <div className="upload-label">Drop PDF here</div>
          <div className="upload-sublabel">or click to browse</div>
          <div className="upload-btns">
            <button
              className="btn btn-dark btn-sm"
              onClick={(e) => { e.stopPropagation(); ref.current?.click(); }}
            >
              Browse File
            </button>
          </div>
        </div>
      ) : (
        <div className="file-preview">
          <div className="file-preview-icon">
            <FileIcon />
          </div>
          <div className="file-preview-info">
            <div className="file-preview-name">{file.name}</div>
            <div className="file-preview-meta">{(file.size / 1024).toFixed(0)} KB · PDF</div>
          </div>
          <div className="file-preview-actions">
            <button className="btn btn-ghost btn-sm" onClick={() => onFile(null)}>
              Remove
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main App ───────────────────────────────────────────────────────────────
export default function App() {

  // ── State ────────────────────────────────────────────────────────────────
  const [questionnaireFile, setQuestionnaireFile] = useState(null);
  const [submissionFile,    setSubmissionFile]    = useState(null);
  const [loading,           setLoading]           = useState(false);
  const [error,             setError]             = useState(null);

  const [mode,            setMode]            = useState(null);
  const [jobResult,       setJobResult]       = useState(null);
  const [evaluations,     setEvaluations]     = useState([]);
  const [annotations,     setAnnotations]     = useState([]);
  const [parsedContent,   setParsedContent]   = useState({ pages: [], tables: [], figures: [] });
  const [pdfFile,         setPdfFile]         = useState(null);
  const [detectionResult, setDetectionResult] = useState(null);
  const [isScanned,       setIsScanned]       = useState(false);
  const [evalProgress,    setEvalProgress]    = useState({ percent: 0, message: "" });

  const canEvaluate = questionnaireFile && submissionFile && !loading;

  // Derive step index: 0=Upload, 1=Evaluate, 2=Results
  const currentStep = (jobResult && !loading) ? 2 : loading ? 1 : 0;

  // Average score across all evaluations
  const avgScore = evaluations.length > 0
    ? evaluations.reduce((s, e) => s + (e.overall_score || 0), 0) / evaluations.length
    : null;

  // ── Run evaluation using same file for both Q and A ───────────────────────
  const runSelfContainedEvaluation = async (uploadResult) => {
    setMode("qa");
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("questionnaire", submissionFile);
      formData.append("submission",    submissionFile);

      const res = await fetch("http://127.0.0.1:8000/text", {
        method: "POST",
        body:   formData,
      });

      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const result = await res.json();
      setJobResult(result);
      const evals = result.evaluations || result.qa_pairs || [];
      setEvaluations(evals);
      console.log("Evaluations received:", evals.length, evals);

    } catch (err) {
      setError(`Evaluation failed: ${err.message}`);
      setMode(null);
    } finally {
      setLoading(false);
    }
  };

  // ── Poll /status until done or error ─────────────────────────────────────
  const pollUntilDone = (jobId) =>
    new Promise((resolve, reject) => {
      const id = setInterval(async () => {
        try {
          const res  = await fetch(`http://127.0.0.1:8000/status/${jobId}`);
          const data = await res.json();
          setEvalProgress({
            percent: data.progress_percent || 0,
            message: data.progress_message || "Processing…",
          });
          if (data.status === "done") {
            clearInterval(id);
            resolve(data);
          } else if (data.status === "error") {
            clearInterval(id);
            reject(new Error(data.error || "Processing failed"));
          }
        } catch (e) {
          clearInterval(id);
          reject(e);
        }
      }, 2500);
    });

  // ── Q&A Evaluation with separate question paper ───────────────────────────
  const handleEvaluate = async () => {
    if (!questionnaireFile || !submissionFile) return;
    setError(null);
    setLoading(true);
    setMode("qa");
    setEvalProgress({ percent: 5, message: "Uploading student submission…" });

    try {
      // POST /upload — returns immediately with job_id
      const uploadForm = new FormData();
      uploadForm.append("file", submissionFile);
      const uploadRes = await fetch("http://127.0.0.1:8000/upload", {
        method: "POST",
        body:   uploadForm,
      });
      if (!uploadRes.ok) throw new Error(`Upload error: ${uploadRes.status}`);
      const { job_id } = await uploadRes.json();

      setEvalProgress({ percent: 10, message: "Processing document on server…" });
      setPdfFile(submissionFile);

      // Poll until the background thread finishes
      const statusData = await pollUntilDone(job_id);

      const scanned = statusData.is_scanned || statusData.ocr_pipeline;
      setIsScanned(scanned);

      if (scanned) {
        setEvalProgress({ percent: 98, message: "Loading annotations…" });
        const fbRes = await fetch(`http://127.0.0.1:8000/feedback/${job_id}`);
        if (!fbRes.ok) throw new Error(`Feedback error: ${fbRes.status}`);
        const fbData = await fbRes.json();

        setJobResult({
          ...statusData,
          job_id,
          submission_filename:    submissionFile.name,
          questionnaire_filename: questionnaireFile.name,
          question_count:         fbData.annotations?.length || 0,
          needs_review_count:     fbData.annotations?.filter(a => a.needs_review).length || 0,
        });
        setAnnotations(fbData.annotations || []);
        setEvaluations([]);

      } else {
        setEvalProgress({ percent: 50, message: "Running Q&A evaluation with Gemini…" });
        const evalForm = new FormData();
        evalForm.append("questionnaire", questionnaireFile);
        evalForm.append("submission",    submissionFile);
        const evalRes = await fetch("http://127.0.0.1:8000/text", {
          method: "POST",
          body:   evalForm,
        });
        if (!evalRes.ok) throw new Error(`Evaluation error: ${evalRes.status}`);
        const evalResult = await evalRes.json();

        setEvalProgress({ percent: 90, message: "Processing evaluation results…" });

        const anns = [];
        let annIndex = 1;
        for (const evaluation of (evalResult.evaluations || [])) {
          for (const item of (evaluation.feedback || [])) {
            if (!item.bbox) continue;
            const bbox = item.bbox;
            anns.push({
              id:            `qa-ann-${annIndex++}`,
              page:          bbox.page || 1,
              questionLabel: evaluation.qa_pair_id || `Q${evaluation.question_number}`,
              bbox: {
                x:      bbox.x0            || 0.05,
                y:      bbox.y0            || 0.05,
                width:  (bbox.x1 - bbox.x0) || 0.9,
                height: (bbox.y1 - bbox.y0) || 0.04,
              },
              region_type:  item.criterion || "answer",
              feedback:     item.comment   || "",
              confidence:   item.confidence || item.score || 0.75,
              needs_review: (item.confidence || 0) < 0.6,
              score:        item.score,
            });
          }
        }

        setJobResult({
          ...evalResult,
          job_id,
          page_count: statusData.page_count,
        });
        setEvaluations(evalResult.evaluations || []);
        setAnnotations(anns);
      }

    } catch (err) {
      setError(`Evaluation failed: ${err.message}`);
      setMode(null);
      setPdfFile(null);
    } finally {
      setEvalProgress({ percent: 100, message: "Complete!" });
      setLoading(false);
    }
  };

  // ── Analyze submission only — with auto question detection ────────────────
  const handleAnalyze = async () => {
    if (!submissionFile) return;
    setError(null);
    setLoading(true);
    setPdfFile(submissionFile);
    setEvalProgress({ percent: 5, message: "Uploading document…" });

    try {
      const formData = new FormData();
      formData.append("file", submissionFile);

      const res = await fetch("http://127.0.0.1:8000/upload", {
        method: "POST",
        body:   formData,
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const { job_id } = await res.json();

      setEvalProgress({ percent: 10, message: "Analyzing document…" });

      // Poll until background processing finishes
      const result    = await pollUntilDone(job_id);
      const detection = result.question_detection || {};

      if (detection.has_questions && detection.verdict === "self_contained" && detection.confidence > 0.8) {
        setJobResult({ ...result, job_id });
        await runSelfContainedEvaluation({ ...result, job_id });
      } else if (!detection.has_questions && detection.verdict === "answers_only" && detection.confidence > 0.8) {
        setJobResult({ ...result, job_id });
        setMode("needs_questionnaire");
      } else {
        setJobResult({ ...result, job_id });
        setDetectionResult(detection);
        setMode("uncertain");
      }

    } catch (err) {
      setError(`Analysis failed: ${err.message}`);
      setPdfFile(null);
      setMode(null);
    } finally {
      setLoading(false);
    }
  };

  // ── Reset ─────────────────────────────────────────────────────────────────
  const handleReset = () => {
    setQuestionnaireFile(null);
    setSubmissionFile(null);
    setLoading(false);
    setError(null);
    setMode(null);
    setJobResult(null);
    setEvaluations([]);
    setAnnotations([]);
    setParsedContent({ pages: [], tables: [], figures: [] });
    setPdfFile(null);
    setDetectionResult(null);
    setIsScanned(false);
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="app">

      {/* HEADER */}
      <header className="app-header">
        <div className="app-header-top">
          <span className="app-logo-mark">M</span>
          <h1>MarginMind</h1>
        </div>
        <p>AI-powered Q&amp;A grading for student submissions.</p>
      </header>

      {/* STEP INDICATOR */}
      <div className="steps">
        {["Upload", "Evaluate", "Results"].map((label, i) => (
          <div
            key={i}
            className={`step${currentStep === i ? " active" : ""}${currentStep > i ? " completed" : ""}`}
          >
            <span className="step-label">{i + 1}. {label}</span>
          </div>
        ))}
      </div>

      {/* UPLOAD SECTION — hide once results are ready */}
      {!jobResult && !loading && (
        <div className="section">
          <div className="section-header">
            <h2 className="section-title">Upload Documents</h2>
            <p className="section-desc">
              Upload both files for Q&amp;A evaluation, or just the submission for document analysis.
            </p>
          </div>

          <div className="upload-row">
            <FileDropZone
              label="📋 Question Paper"
              desc="Upload the question paper PDF (optional)"
              file={questionnaireFile}
              onFile={setQuestionnaireFile}
            />
            <FileDropZone
              label="📝 Student Submission"
              desc="Upload the student answer PDF"
              file={submissionFile}
              onFile={setSubmissionFile}
            />
          </div>

          <div className="upload-actions">
            <button
              className="grade-btn"
              onClick={handleEvaluate}
              disabled={!canEvaluate}
            >
              {canEvaluate
                ? "⚡ Grade with Q&A Evaluation"
                : questionnaireFile && !submissionFile
                  ? "Upload student submission to continue"
                  : !questionnaireFile && submissionFile
                    ? "Upload question paper for Q&A evaluation"
                    : "Upload both files to evaluate"}
            </button>

            {submissionFile && !questionnaireFile && (
              <button className="btn btn-ghost analyze-btn" onClick={handleAnalyze}>
                Analyze Document Only
              </button>
            )}
          </div>

          {error && <div className="error-box">{error}</div>}
        </div>
      )}

      {/* LOADING */}
      {loading && (
        <div className="section">
          <div className="loading-wrap">
            <div className="loader" />
            <div className="loading-label">
              {mode === "qa"
                ? evalProgress.message || "Running Q&A evaluation with Gemini…"
                : "Analyzing document and detecting questions…"}
            </div>
            {mode === "qa" && (
              <>
                <div className="eval-progress-bar-wrap">
                  <div
                    className="eval-progress-bar-fill"
                    style={{ width: `${evalProgress.percent}%` }}
                  />
                </div>
                <div className="eval-steps">
                  {QA_STEPS.map((step, i) => {
                    const done   = evalProgress.percent > step.doneAt;
                    const active = !done && (i === 0 || evalProgress.percent > QA_STEPS[i - 1].doneAt);
                    return (
                      <div key={i} className={`eval-step${done ? " done" : active ? " active" : ""}`}>
                        <span className="eval-step-icon">{done ? "✓" : active ? "⟳" : "○"}</span>
                        <span className="eval-step-label">{step.label}</span>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* RESULTS */}
      {jobResult && !loading && (
        <>
          {/* Info bar */}
          <div className="result-info-bar">
            <div className="result-info-meta">
              {mode === "qa" ? (
                <>
                  <span className="result-filename">{jobResult.submission_filename}</span>
                  <span className="result-sep">vs</span>
                  <span className="result-filename">{jobResult.questionnaire_filename}</span>
                  <span className="result-detail">
                    {isScanned
                      ? `${jobResult.question_count || annotations.length} regions · OCR`
                      : `${jobResult.question_count} questions evaluated`}
                    {jobResult.needs_review_count > 0 && ` · ${jobResult.needs_review_count} flagged`}
                  </span>
                </>
              ) : (
                <>
                  <span className="result-filename">{jobResult.filename}</span>
                  <span className="result-detail">
                    {jobResult.page_count} page{jobResult.page_count !== 1 ? "s" : ""}
                    {jobResult.table_count > 0 && ` · ${jobResult.table_count} table${jobResult.table_count !== 1 ? "s" : ""}`}
                    {jobResult.figure_count > 0 && ` · ${jobResult.figure_count} figure${jobResult.figure_count !== 1 ? "s" : ""}`}
                  </span>
                </>
              )}
            </div>
            <div className="result-info-right">
              {avgScore !== null && (
                <div className={`score-pill ${avgScore >= 0.7 ? "good" : avgScore >= 0.4 ? "avg" : "poor"}`}>
                  {Math.round(avgScore * 100)}%
                </div>
              )}
              <button className="btn btn-ghost btn-sm" onClick={handleReset}>
                ← Start Over
              </button>
            </div>
          </div>

          {/* UNCERTAIN DETECTION */}
          {mode === "uncertain" && detectionResult && (
            <div style={{
              marginTop: "16px", padding: "20px 24px",
              background: "#fffbeb", border: "1px solid #fde68a",
              borderRadius: "10px",
            }}>
              <div style={{ fontWeight: "700", fontSize: "0.95rem", color: "#92400e", marginBottom: "8px" }}>
                ⚡ We're not sure about this document
              </div>
              <p style={{ fontSize: "0.85rem", color: "#78350f", marginBottom: "4px", lineHeight: "1.6" }}>
                {detectionResult.reasoning}
              </p>
              <p style={{ fontSize: "0.78rem", color: "#92400e", marginBottom: "16px", fontFamily: "monospace" }}>
                Confidence: {Math.round((detectionResult.confidence || 0) * 100)}%
                &nbsp;·&nbsp;
                Verdict: {detectionResult.verdict}
              </p>
              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                <button onClick={() => runSelfContainedEvaluation(jobResult)} className="btn btn-dark">
                  ✓ Evaluate without question paper
                </button>
                <button
                  onClick={() => setMode("needs_questionnaire")}
                  style={{
                    padding: "10px 20px", background: "none",
                    color: "#92400e", border: "1px solid #fcd34d",
                    borderRadius: "8px", fontSize: "0.85rem",
                    fontWeight: "600", cursor: "pointer",
                  }}
                >
                  📋 Upload question paper instead
                </button>
              </div>
            </div>
          )}

          {/* NEEDS QUESTIONNAIRE */}
          {mode === "needs_questionnaire" && (
            <div style={{
              marginTop: "16px", padding: "20px 24px",
              background: "#f5f3ff", border: "1px solid #a78bfa",
              borderRadius: "10px",
            }}>
              <div style={{ fontWeight: "700", fontSize: "0.95rem", color: "#5b21b6", marginBottom: "8px" }}>
                📋 Question paper needed
              </div>
              <p style={{ fontSize: "0.85rem", color: "#6d28d9", marginBottom: "16px", lineHeight: "1.6" }}>
                This submission appears to contain only answers.
                Upload the question paper to run a full Q&A evaluation.
              </p>
              <div style={{ maxWidth: "400px" }}>
                <FileDropZone
                  label="Question Paper"
                  desc="Upload the question paper PDF"
                  file={questionnaireFile}
                  onFile={setQuestionnaireFile}
                />
              </div>
              {questionnaireFile && (
                <button
                  onClick={handleEvaluate}
                  disabled={loading}
                  className="btn btn-dark"
                  style={{ marginTop: "16px" }}
                >
                  ⚡ Grade with Q&A Evaluation
                </button>
              )}
            </div>
          )}

          {/* SINGLE PDF RESULTS */}
          {mode === "single" && (
            <>
              <PDFViewer
                pdfFile={pdfFile}
                annotations={annotations}
                jobId={jobResult?.job_id}
                pageCount={jobResult?.page_count || 1}
              />
              <ParsedContent parsed={parsedContent} />
            </>
          )}

          {/* Q&A PDF VIEWER WITH OVERLAYS */}
          {mode === "qa" && pdfFile && jobResult?.job_id && (
            <div style={{ marginTop: "24px" }}>
              <PDFViewer
                pdfFile={pdfFile}
                annotations={annotations}
                jobId={jobResult?.job_id}
                pageCount={jobResult?.page_count || 1}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}
