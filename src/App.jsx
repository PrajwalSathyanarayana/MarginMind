import { useState } from "react";
import "./App.css";
import PDFViewer from "./components/PDFViewer";
import ParsedContent from "./components/ParsedContent";

// ── File drop zone component ───────────────────────────────────────────────
function FileDropZone({ label, desc, file, onFile, accept = "application/pdf" }) {
  const [dragover, setDragover] = useState(false);
  const ref = { current: null };

  const handleFile = (f) => { if (!f) return; onFile(f); };

  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontWeight: "700", fontSize: "0.9rem", color: "#1a1a2e", marginBottom: "4px" }}>
        {label}
      </div>
      <div style={{ fontSize: "0.78rem", color: "#9a9888", marginBottom: "10px" }}>
        {desc}
      </div>
      <input
        ref={(el) => (ref.current = el)}
        type="file"
        accept={accept}
        style={{ display: "none" }}
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      {!file ? (
        <div
          onClick={() => ref.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragover(true); }}
          onDragLeave={() => setDragover(false)}
          onDrop={(e) => { e.preventDefault(); setDragover(false); handleFile(e.dataTransfer.files?.[0]); }}
          style={{
            border: `2px dashed ${dragover ? "#7c5cfc" : "#d0cec6"}`,
            borderRadius: "10px", padding: "32px 20px",
            textAlign: "center", cursor: "pointer",
            background: dragover ? "#f5f3ff" : "#fafaf7",
            transition: "all 0.2s",
          }}
        >
          <div style={{ fontSize: "1.8rem", marginBottom: "8px" }}>📄</div>
          <div style={{ fontSize: "0.82rem", color: "#6b6960", marginBottom: "6px" }}>
            Drop PDF here or click to browse
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); ref.current?.click(); }}
            style={{
              marginTop: "8px", padding: "7px 18px",
              background: "#1a1a2e", color: "#fff",
              border: "none", borderRadius: "6px",
              fontSize: "0.8rem", cursor: "pointer",
            }}
          >
            Browse File
          </button>
        </div>
      ) : (
        <div style={{
          border: "1px solid #4ade80", borderRadius: "10px",
          padding: "16px 20px", background: "#f0fdf4",
          display: "flex", alignItems: "center",
          justifyContent: "space-between", gap: "12px",
        }}>
          <div>
            <div style={{ fontSize: "0.85rem", fontWeight: "600", color: "#166534", marginBottom: "2px" }}>
              ✓ {file.name}
            </div>
            <div style={{ fontSize: "0.72rem", color: "#9a9888" }}>
              {(file.size / 1024).toFixed(0)} KB
            </div>
          </div>
          <button
            onClick={() => onFile(null)}
            style={{
              background: "none", border: "1px solid #d0cec6",
              borderRadius: "6px", padding: "4px 10px",
              fontSize: "0.75rem", cursor: "pointer", color: "#6b6960",
            }}
          >
            Remove
          </button>
        </div>
      )}
    </div>
  );
}

// ── Score badge ────────────────────────────────────────────────────────────
function ScoreBadge({ score }) {
  const pct   = Math.round(score * 100);
  const color = pct >= 70 ? "#166534" : pct >= 40 ? "#92400e" : "#991b1b";
  const bg    = pct >= 70 ? "#dcfce7" : pct >= 40 ? "#fef9c3" : "#fee2e2";
  return (
    <span style={{
      fontFamily: "monospace", fontSize: "0.85rem", fontWeight: "700",
      color, background: bg, padding: "3px 10px",
      borderRadius: "99px", border: `1px solid ${color}33`,
    }}>
      {pct}%
    </span>
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
  const [detectionResult, setDetectionResult] = useState(null);  // ← inside App ✅

  const canEvaluate = questionnaireFile && submissionFile && !loading;

  // ── Run evaluation using same file for both Q and A ───────────────────────
  const runSelfContainedEvaluation = async (uploadResult) => {  // ← inside App ✅
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
      setEvaluations(result.evaluations || []);

    } catch (err) {
      setError(`Evaluation failed: ${err.message}`);
      setMode(null);
    } finally {
      setLoading(false);
    }
  };

  // ── Q&A Evaluation with separate question paper ───────────────────────────
  const handleEvaluate = async () => {
    if (!questionnaireFile || !submissionFile) return;
    setError(null);
    setLoading(true);
    setMode("qa");

    try {
      const formData = new FormData();
      formData.append("questionnaire", questionnaireFile);
      formData.append("submission",    submissionFile);

      const res = await fetch("http://127.0.0.1:8000/text", {
        method: "POST",
        body:   formData,
      });

      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const result = await res.json();
      setJobResult(result);
      setEvaluations(result.evaluations || []);

    } catch (err) {
      setError(`Evaluation failed: ${err.message}`);
      setMode(null);
    } finally {
      setLoading(false);
    }
  };

  // ── Analyze submission only — with auto question detection ────────────────
  const handleAnalyze = async () => {
    if (!submissionFile) return;
    setError(null);
    setLoading(true);
    setPdfFile(submissionFile);

    try {
      const formData = new FormData();
      formData.append("file", submissionFile);

      const res = await fetch("http://127.0.0.1:8000/upload", {
        method: "POST",
        body:   formData,
      });

      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const result   = await res.json();
      const detection = result.question_detection || {};

      if (
        detection.has_questions &&
        detection.verdict === "self_contained" &&
        detection.confidence > 0.8
      ) {
        // Self-contained — evaluate directly
        setJobResult(result);
        await runSelfContainedEvaluation(result);

      } else if (
        !detection.has_questions &&
        detection.verdict === "answers_only" &&
        detection.confidence > 0.8
      ) {
        // Clearly answers only — prompt for questionnaire
        setJobResult(result);
        setMode("needs_questionnaire");

      } else {
        // Uncertain — ask user
        setJobResult(result);
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
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="app">

      {/* HEADER */}
      <header className="app-header">
        <h1>MarginMind</h1>
        <p>Upload assignments to get AI-powered feedback.</p>
      </header>

      {/* UPLOAD SECTION — hide once results are ready */}
      {!jobResult && !loading && (
        <div className="section">
          <div className="section-header">
            <h2 className="section-title">Upload Documents</h2>
            <p className="section-desc">
              Upload both files for Q&A evaluation, or just the submission for document analysis.
            </p>
          </div>

          <div style={{ display: "flex", gap: "20px", marginTop: "16px" }}>
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

          <div style={{ marginTop: "20px", display: "flex", gap: "12px" }}>
            <button
              onClick={handleEvaluate}
              disabled={!canEvaluate}
              style={{
                flex: 1, padding: "12px 24px",
                background: canEvaluate ? "#1a1a2e" : "#e8e6de",
                color: canEvaluate ? "#fff" : "#9a9888",
                border: "none", borderRadius: "8px",
                fontSize: "0.9rem", fontWeight: "600",
                cursor: canEvaluate ? "pointer" : "not-allowed",
                transition: "all 0.2s",
              }}
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
              <button
                onClick={handleAnalyze}
                style={{
                  padding: "12px 20px", background: "none",
                  color: "#5b21b6", border: "1px solid #a78bfa",
                  borderRadius: "8px", fontSize: "0.85rem",
                  fontWeight: "600", cursor: "pointer",
                }}
              >
                Analyze Document Only
              </button>
            )}
          </div>

          {error && (
            <div style={{
              marginTop: "12px", padding: "10px 14px",
              background: "#3b1a1a", border: "1px solid #7f1d1d",
              borderRadius: "6px", color: "#f87171", fontSize: "0.85rem",
            }}>
              {error}
            </div>
          )}
        </div>
      )}

      {/* LOADING */}
      {loading && (
        <div className="section">
          <div className="loading-wrap">
            <div className="loader" />
            <div className="loading-label">
              {mode === "qa"
                ? "Running Q&A evaluation with Gemini…"
                : "Analyzing document and detecting questions…"}
            </div>
          </div>
        </div>
      )}

      {/* RESULTS */}
      {jobResult && !loading && (
        <>
          {/* Info bar */}
          <div style={{
            display: "flex", justifyContent: "space-between",
            alignItems: "center", padding: "10px 16px",
            background: "#f0efe9", border: "1px solid #e0ddd6",
            borderRadius: "8px", marginTop: "16px",
          }}>
            <div style={{ fontSize: "0.85rem", color: "#3d3b30" }}>
              {mode === "qa" ? (
                <>
                  <strong>{jobResult.submission_filename}</strong>
                  <span style={{ color: "#9a9888", marginLeft: "8px" }}>vs</span>
                  <strong style={{ marginLeft: "8px" }}>{jobResult.questionnaire_filename}</strong>
                  <span style={{ color: "#9a9888", marginLeft: "12px" }}>
                    {jobResult.question_count} questions evaluated
                    {jobResult.needs_review_count > 0 &&
                      ` · ${jobResult.needs_review_count} flagged for review`}
                  </span>
                </>
              ) : (
                <>
                  <strong>{jobResult.filename}</strong>
                  <span style={{ color: "#9a9888", marginLeft: "12px" }}>
                    {jobResult.page_count} page{jobResult.page_count !== 1 ? "s" : ""}
                    {jobResult.table_count > 0 &&
                      ` · ${jobResult.table_count} table${jobResult.table_count !== 1 ? "s" : ""}`}
                    {jobResult.figure_count > 0 &&
                      ` · ${jobResult.figure_count} figure${jobResult.figure_count !== 1 ? "s" : ""}`}
                  </span>
                </>
              )}
            </div>
            <button onClick={handleReset} style={{
              background: "none", border: "1px solid #d0cec6",
              borderRadius: "6px", padding: "5px 12px",
              fontSize: "0.8rem", cursor: "pointer", color: "#6b6960",
            }}>
              ← Start Over
            </button>
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
                <button
                  onClick={() => runSelfContainedEvaluation(jobResult)}
                  style={{
                    padding: "10px 20px", background: "#1a1a2e",
                    color: "#fff", border: "none", borderRadius: "8px",
                    fontSize: "0.85rem", fontWeight: "600", cursor: "pointer",
                  }}
                >
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
                  style={{
                    marginTop: "16px", padding: "10px 24px",
                    background: "#1a1a2e", color: "#fff",
                    border: "none", borderRadius: "8px",
                    fontSize: "0.85rem", fontWeight: "600", cursor: "pointer",
                  }}
                >
                  ⚡ Grade with Q&A Evaluation
                </button>
              )}
            </div>
          )}

          {/* Q&A EVALUATION RESULTS */}
          {mode === "qa" && evaluations.length > 0 && (
            <div className="section" style={{ marginTop: "16px" }}>
              <div className="section-header" style={{
                display: "flex", justifyContent: "space-between", alignItems: "flex-start"
              }}>
                <div>
                  <h2 className="section-title">Evaluation Results</h2>
                  <p className="section-desc">{evaluations.length} questions graded by Gemini</p>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{
                    fontSize: "0.7rem", color: "#9a9888",
                    textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "4px"
                  }}>
                    Overall Score
                  </div>
                  <ScoreBadge
                    score={
                      evaluations.reduce((sum, e) => sum + (e.overall_score || 0), 0)
                      / evaluations.length
                    }
                  />
                </div>
              </div>

              {evaluations.map((evaluation, i) => (
                <div key={evaluation.id || i} style={{
                  background: "#fff", border: "1px solid #e8e6de",
                  borderRadius: "10px", padding: "16px 20px", marginBottom: "12px",
                  borderLeft: `4px solid ${
                    evaluation.overall_score >= 0.7 ? "#4ade80"
                    : evaluation.overall_score >= 0.4 ? "#fbbf24" : "#f87171"
                  }`,
                }}>
                  <div style={{
                    display: "flex", justifyContent: "space-between",
                    alignItems: "center", marginBottom: "12px",
                  }}>
                    <div>
                      <span style={{ fontWeight: "700", fontSize: "0.95rem", color: "#1a1a2e", marginRight: "10px" }}>
                        Question {evaluation.question_number}
                      </span>
                      <span style={{
                        fontSize: "0.7rem", padding: "2px 8px", borderRadius: "4px",
                        background: "#ede9fe", color: "#5b21b6", fontWeight: "600",
                      }}>
                        {evaluation.selected_criteria}
                      </span>
                    </div>
                    <ScoreBadge score={evaluation.overall_score || 0} />
                  </div>

                  {evaluation.feedback?.map((item, j) => (
                    <div key={j} style={{
                      background: "#fafaf7", borderRadius: "8px",
                      padding: "12px 14px", marginBottom: "8px",
                      border: "1px solid #f0efe9",
                    }}>
                      {item.highlight_phrase && (
                        <div style={{
                          fontStyle: "italic", fontSize: "0.8rem", color: "#5b21b6",
                          marginBottom: "8px", padding: "6px 10px", background: "#ede9fe",
                          borderRadius: "6px", lineHeight: "1.5", borderLeft: "3px solid #7c5cfc",
                        }}>
                          "{item.highlight_phrase}"
                        </div>
                      )}
                      <p style={{ fontSize: "0.83rem", color: "#3d3b30", lineHeight: "1.65", margin: "0 0 10px" }}>
                        {item.comment}
                      </p>
                      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                        <span style={{
                          fontSize: "0.65rem", padding: "2px 7px", borderRadius: "4px",
                          background: "#ede9fe", color: "#5b21b6", fontWeight: "600",
                          textTransform: "uppercase",
                        }}>
                          {item.criterion}
                        </span>
                        <span style={{
                          fontSize: "0.65rem", padding: "2px 7px", borderRadius: "4px", fontWeight: "600",
                          background: item.score >= 0.7 ? "#dcfce7" : item.score >= 0.4 ? "#fef9c3" : "#fee2e2",
                          color: item.score >= 0.7 ? "#166534" : item.score >= 0.4 ? "#92400e" : "#991b1b",
                        }}>
                          Score: {Math.round((item.score || 0) * 100)}%
                        </span>
                        <span style={{
                          fontSize: "0.65rem", padding: "2px 7px", borderRadius: "4px", fontWeight: "600",
                          background: (item.confidence || 0) > 0.8 ? "#dcfce7" : "#fef9c3",
                          color: (item.confidence || 0) > 0.8 ? "#166534" : "#92400e",
                        }}>
                          {Math.round((item.confidence || 0) * 100)}% confidence
                        </span>
                      </div>
                    </div>
                  ))}

                  {evaluation.needs_review && (
                    <div style={{
                      marginTop: "8px", fontSize: "0.75rem", color: "#b45309",
                      background: "#fef3c7", border: "1px solid #fde68a",
                      borderRadius: "4px", padding: "4px 10px", display: "inline-block",
                    }}>
                      ⚠ Needs Instructor Review
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* SINGLE PDF RESULTS */}
          {mode === "single" && (
            <>
              <PDFViewer pdfFile={pdfFile} annotations={annotations} />
              <ParsedContent parsed={parsedContent} />
            </>
          )}
        </>
      )}
    </div>
  );
}