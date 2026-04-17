import { useEffect, useRef, useState } from "react";

export default function PDFViewer({ pdfFile, annotations = [], jobId = null, pageCount = 1 }) {
  const [currentPage,   setCurrentPage]   = useState(1);
  const [pageImageUrl,  setPageImageUrl]  = useState(null);
  const [imgDimensions, setImgDimensions] = useState({ width: 0, height: 0 });
  const [activeAnnotation, setActiveAnnotation] = useState(null);
  const [loadingPage,   setLoadingPage]   = useState(false);
  const imgRef = useRef(null);

  const totalPages = pageCount || 1;

  // ── Fetch page image from backend ────────────────────────────────────
  useEffect(() => {
    if (!jobId) return;
    setLoadingPage(true);
    setPageImageUrl(null);

    fetch(`http://127.0.0.1:8000/page/${jobId}/${currentPage}`)
      .then(res => {
        if (!res.ok) throw new Error("Page not found");
        return res.blob();
      })
      .then(blob => {
        const url = URL.createObjectURL(blob);
        setPageImageUrl(url);
      })
      .catch(() => setPageImageUrl(null))
      .finally(() => setLoadingPage(false));

    return () => {
      if (pageImageUrl) URL.revokeObjectURL(pageImageUrl);
    };
  }, [jobId, currentPage]);

  // ── Track image dimensions for overlay positioning ────────────────────
  useEffect(() => {
    if (!imgRef.current) return;
    const observer = new ResizeObserver(() => {
      if (imgRef.current) {
        setImgDimensions({
          width:  imgRef.current.clientWidth,
          height: imgRef.current.clientHeight,
        });
      }
    });
    observer.observe(imgRef.current);
    return () => observer.disconnect();
  }, [pageImageUrl]);

  // ── Filter annotations for current page ──────────────────────────────
  const pageAnnotations = annotations.filter(a => a.page === currentPage);

  // ── Score color helper ────────────────────────────────────────────────
const scoreColor = (score) => {
    if (score >= 0.75) return { bg: "rgba(74,222,128,0.25)",  border: "#4ade80" };
    if (score >= 0.4) return { bg: "rgba(251,191,36,0.25)",  border: "#fbbf24" };
    return                   { bg: "rgba(248,113,113,0.25)", border: "#f87171" };
};

  return (
    <div style={styles.wrapper}>

      {/* ── LEFT MARGIN PANEL ─────────────────────────────────────── */}
      <div style={styles.marginPanel}>
        <div style={styles.marginHeader}>
          <span style={styles.marginTitle}>Feedback</span>
          <span style={styles.marginPage}>Page {currentPage}</span>
        </div>

        <div style={styles.marginBody}>
          {pageAnnotations.length === 0 ? (
            <div style={styles.emptyState}>
              <div style={{ fontSize: "1.8rem", marginBottom: "10px", opacity: 0.4 }}>💬</div>
              <p style={styles.emptyText}>No feedback for this page.</p>
              <p style={styles.emptySubtext}>
                Gemini-generated comments will appear here.
              </p>
            </div>
          ) : (
            pageAnnotations.map((ann, i) => {
              const colors  = scoreColor(ann.score ?? ann.confidence);
              const isActive = activeAnnotation?.id === ann.id;
              return (
                <div
                  key={ann.id || i}
                  onClick={() => setActiveAnnotation(isActive ? null : ann)}
                  style={{
                    ...styles.annotationCard,
                    borderLeft: `3px solid ${colors.border}`,
                    background: isActive ? "#f0efe9" : "#fff",
                    cursor: "pointer",
                  }}
                >
                  {/* Question label + region type + score */}
                  <div style={styles.annotationMeta}>
                    {ann.questionLabel && (
                      <span style={{
                        ...styles.regionBadge,
                        background: "#1a1a2e", color: "#fff",
                        marginRight: "2px",
                      }}>
                        {ann.questionLabel}
                      </span>
                    )}
                    <span style={{
                      ...styles.regionBadge,
                      background: "#ede9fe", color: "#5b21b6",
                    }}>
                      {ann.region_type}
                    </span>
                    <span style={{
                      ...styles.confidenceBadge,
                      background: colors.bg,
                      color: colors.border,
                      border: `1px solid ${colors.border}`,
                    }}>
                      {Math.round((ann.score ?? ann.confidence) * 100)}%
                    </span>
                  </div>

                  {/* Feedback text */}
                  <p style={styles.feedbackText}>{ann.feedback}</p>

                  {/* Needs review flag */}
                  {ann.needs_review && (
                    <div style={styles.reviewFlag}>⚠ Needs Review</div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* ── PDF PAGE + OVERLAYS ───────────────────────────────────── */}
      <div style={styles.pdfPanel}>

        {/* Navigation bar */}
        <div style={styles.navBar}>
          <button
            style={styles.navBtn}
            onClick={() => { setCurrentPage(p => Math.max(1, p - 1)); setActiveAnnotation(null); }}
            disabled={currentPage === 1}
          >
            ← Prev
          </button>
          <span style={styles.pageIndicator}>Page {currentPage} of {totalPages}</span>
          <button
            style={styles.navBtn}
            onClick={() => { setCurrentPage(p => Math.min(totalPages, p + 1)); setActiveAnnotation(null); }}
            disabled={currentPage === totalPages}
          >
            Next →
          </button>
        </div>

        {/* Page image + annotation overlays */}
        <div style={styles.pageContainer}>
          {loadingPage && (
            <div style={styles.loadingOverlay}>
              <div style={{ color: "#9a9888", fontSize: "0.85rem" }}>Loading page…</div>
            </div>
          )}

          {/* Fallback to iframe if no job_id or page image fails */}
          {!jobId && pdfFile && (
            <iframe
              src={URL.createObjectURL(pdfFile) + `#page=${currentPage}`}
              style={styles.iframe}
              title="PDF"
            />
          )}

          {/* Image-based rendering with overlays */}
          {pageImageUrl && (
            <div style={{ position: "relative", display: "inline-block", width: "100%" }}>
              <img
                ref={imgRef}
                src={pageImageUrl}
                alt={`Page ${currentPage}`}
                style={styles.pageImage}
                onLoad={() => {
                  if (imgRef.current) {
                    setImgDimensions({
                      width:  imgRef.current.clientWidth,
                      height: imgRef.current.clientHeight,
                    });
                  }
                }}
              />

              {/* Draw highlight overlay for each annotation on this page */}
              {imgDimensions.width > 0 && pageAnnotations.map((ann, i) => {
                const bbox   = ann.bbox;
                if (!bbox) return null;

                const colors  = scoreColor(ann.score ?? ann.confidence);
                const isActive = activeAnnotation?.id === ann.id;

                // bbox coordinates are normalized 0-1
                // multiply by actual rendered image dimensions
                const left   = (bbox.x      || bbox.x0 || 0) * imgDimensions.width;
                const top    = (bbox.y       || bbox.y0 || 0) * imgDimensions.height;
                const width  = (bbox.width  || (bbox.x1 - bbox.x0) || 0.9) * imgDimensions.width;
                const height = (bbox.height || (bbox.y1 - bbox.y0) || 0.05) * imgDimensions.height;

                return (
                  <div
                    key={ann.id || i}
                    onClick={() => setActiveAnnotation(isActive ? null : ann)}
                    title={ann.feedback}
                    style={{
                      position:     "absolute",
                      left:         `${left}px`,
                      top:          `${top}px`,
                      width:        `${Math.max(width, 20)}px`,
                      height:       `${Math.max(height, 8)}px`,
                      background:   isActive ? colors.bg : `${colors.bg}`,
                      border:       `1px solid ${colors.border}`,
                      borderRadius: "2px",
                      cursor:       "pointer",
                      opacity:      isActive ? 1 : 0.6,
                      transition:   "opacity 0.15s, background 0.15s",
                      zIndex:       10,
                      // Score label on the right edge of highlight
                    }}
                  >
                    {/* Small score label */}
                    <span style={{
                      position:   "absolute",
                      right:      "-2px",
                      top:        "-16px",
                      background: colors.border,
                      color:      "#fff",
                      fontSize:   "0.58rem",
                      fontWeight: "700",
                      padding:    "1px 4px",
                      borderRadius: "3px",
                      fontFamily: "monospace",
                      whiteSpace: "nowrap",
                      pointerEvents: "none",
                    }}>
                      {Math.round((ann.score ?? ann.confidence) * 100)}%
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────
const styles = {
  wrapper: {
    display:      "flex",
    flexDirection: "row",
    width:        "100%",
    height:       "calc(100vh - 180px)",
    background:   "#f5f5f0",
    borderRadius: "12px",
    overflow:     "hidden",
    border:       "1px solid #e0ddd6",
    marginTop:    "16px",
  },
  marginPanel: {
    width:        "280px",
    minWidth:     "280px",
    background:   "#fafaf7",
    borderRight:  "1px solid #e0ddd6",
    display:      "flex",
    flexDirection: "column",
    overflow:     "hidden",
  },
  marginHeader: {
    display:        "flex",
    justifyContent: "space-between",
    alignItems:     "center",
    padding:        "14px 16px",
    borderBottom:   "1px solid #e0ddd6",
    background:     "#f0efe9",
    flexShrink:     0,
  },
  marginTitle: {
    fontSize:      "0.78rem",
    fontWeight:    "700",
    color:         "#3d3b30",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  },
  marginPage: {
    fontSize:   "0.72rem",
    color:      "#9a9888",
    fontFamily: "monospace",
  },
  marginBody: {
    flex:       1,
    overflowY:  "auto",
    padding:    "12px",
  },
  emptyState: {
    display:        "flex",
    flexDirection:  "column",
    alignItems:     "center",
    justifyContent: "center",
    padding:        "40px 16px",
    textAlign:      "center",
    height:         "100%",
  },
  emptyText: {
    fontSize:   "0.82rem",
    color:      "#6b6960",
    marginBottom: "6px",
    lineHeight: "1.5",
  },
  emptySubtext: {
    fontSize:   "0.72rem",
    color:      "#9a9888",
    lineHeight: "1.5",
  },
  annotationCard: {
    background:   "#fff",
    border:       "1px solid #e8e6de",
    borderRadius: "8px",
    padding:      "10px 12px",
    marginBottom: "10px",
    transition:   "background 0.15s",
  },
  annotationMeta: {
    display:      "flex",
    gap:          "6px",
    marginBottom: "7px",
    flexWrap:     "wrap",
  },
  regionBadge: {
    fontSize:      "0.6rem",
    padding:       "2px 7px",
    borderRadius:  "4px",
    fontWeight:    "600",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  confidenceBadge: {
    fontSize:     "0.6rem",
    padding:      "2px 7px",
    borderRadius: "4px",
    fontWeight:   "600",
  },
  feedbackText: {
    fontSize:   "0.8rem",
    color:      "#3d3b30",
    lineHeight: "1.6",
    margin:     "0",
  },
  reviewFlag: {
    marginTop:    "7px",
    fontSize:     "0.7rem",
    color:        "#b45309",
    background:   "#fef3c7",
    border:       "1px solid #fde68a",
    borderRadius: "4px",
    padding:      "3px 8px",
    display:      "inline-block",
  },
  pdfPanel: {
    flex:          1,
    display:       "flex",
    flexDirection: "column",
    background:    "#e8e6df",
    minWidth:      0,
    overflow:      "hidden",
  },
  navBar: {
    display:        "flex",
    alignItems:     "center",
    justifyContent: "center",
    gap:            "16px",
    padding:        "10px 16px",
    background:     "#f0efe9",
    borderBottom:   "1px solid #e0ddd6",
    flexShrink:     0,
  },
  navBtn: {
    background:   "#fff",
    border:       "1px solid #d0cec6",
    borderRadius: "6px",
    padding:      "5px 14px",
    fontSize:     "0.8rem",
    cursor:       "pointer",
    color:        "#3d3b30",
  },
  pageIndicator: {
    fontSize:   "0.8rem",
    color:      "#6b6960",
    fontFamily: "monospace",
  },
  pageContainer: {
    flex:           1,
    overflowY:      "auto",
    display:        "flex",
    justifyContent: "center",
    padding:        "20px",
    background:     "#e8e6df",
  },
  loadingOverlay: {
    display:        "flex",
    alignItems:     "center",
    justifyContent: "center",
    height:         "200px",
    width:          "100%",
  },
  pageImage: {
    width:     "100%",
    height:    "auto",
    display:   "block",
    boxShadow: "0 2px 12px rgba(0,0,0,0.15)",
    background: "#fff",
  },
  iframe: {
    flex:    1,
    width:   "100%",
    height:  "100%",
    border:  "none",
    display: "block",
  },
};