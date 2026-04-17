import { useEffect, useRef, useState, useCallback } from "react";

export default function PDFViewer({ pdfFile, annotations = [], jobId = null, pageCount = 1 }) {
  const [currentPage,    setCurrentPage]    = useState(1);
  const [pageImageUrl,   setPageImageUrl]   = useState(null);
  const [imgDimensions,  setImgDimensions]  = useState({ width: 0, height: 0 });
  const [activeAnnotation, setActiveAnnotation] = useState(null);
  const [loadingPage,    setLoadingPage]    = useState(false);

  const imgRef        = useRef(null);
  const pdfPanelRef   = useRef(null);
  const marginBodyRef = useRef(null);
  const cardRefs      = useRef({});
  const isSyncingRef  = useRef(false); // prevents scroll feedback loops

  const totalPages = pageCount || 1;

  // ── Fetch page image ───────────────────────────────────────────────
  useEffect(() => {
    if (!jobId) return;
    setLoadingPage(true);
    setPageImageUrl(null);

    let objectUrl = null;
    fetch(`http://127.0.0.1:8000/page/${jobId}/${currentPage}`)
      .then(res => { if (!res.ok) throw new Error("Page not found"); return res.blob(); })
      .then(blob => { objectUrl = URL.createObjectURL(blob); setPageImageUrl(objectUrl); })
      .catch(() => setPageImageUrl(null))
      .finally(() => setLoadingPage(false));

    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [jobId, currentPage]);

  // ── Track image render dimensions ─────────────────────────────────
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

  const pageAnnotations = annotations.filter(a => a.page === currentPage);

  // ── Find which annotation is closest to current scroll position ────
  const getActiveAnnotationFromScroll = useCallback(() => {
    if (!pdfPanelRef.current || !imgRef.current || imgDimensions.height === 0) return null;

    const panelScrollTop = pdfPanelRef.current.scrollTop;
    const panelHeight    = pdfPanelRef.current.clientHeight;
    // Center of the visible PDF viewport as a fraction of image height
    const viewCenterY    = (panelScrollTop + panelHeight * 0.35) / imgDimensions.height;

    if (pageAnnotations.length === 0) return null;

    // Find closest annotation to the center of the viewport
    let closest     = null;
    let closestDist = Infinity;

    for (const ann of pageAnnotations) {
      const bbox   = ann.bbox;
      if (!bbox) continue;
      const annY   = (bbox.y || bbox.y0 || 0) + (bbox.height || 0) / 2;
      const dist   = Math.abs(annY - viewCenterY);
      if (dist < closestDist) {
        closestDist = dist;
        closest     = ann;
      }
    }

    return closest;
  }, [pageAnnotations, imgDimensions]);

  // ── Scroll feedback card into view ─────────────────────────────────
const scrollCardIntoView = useCallback((annId) => {
    if (!annId || !marginBodyRef.current) return;
    const card = cardRefs.current[annId];
    if (!card) return;

    const container       = marginBodyRef.current;
    const containerHeight = container.clientHeight;
    const cardTop         = card.offsetTop;
    const cardHeight      = card.clientHeight;

    // Center the card in the panel
    const targetScrollTop = cardTop - (containerHeight / 2) + (cardHeight / 2);

    isSyncingRef.current = true;
    container.scrollTo({
      top:      Math.max(0, targetScrollTop),
      behavior: "smooth",
    });
    setTimeout(() => { isSyncingRef.current = false; }, 600);
}, []);

  // ── PDF scroll handler — syncs left panel ─────────────────────────
  const handlePdfScroll = useCallback(() => {
    if (isSyncingRef.current) return;
    const active = getActiveAnnotationFromScroll();
    if (active && active.id !== activeAnnotation?.id) {
      setActiveAnnotation(active);
      scrollCardIntoView(active.id);
    }
  }, [getActiveAnnotationFromScroll, activeAnnotation, scrollCardIntoView]);

  // ── Attach scroll listener to PDF panel ───────────────────────────
  useEffect(() => {
    const panel = pdfPanelRef.current;
    if (!panel) return;
    panel.addEventListener("scroll", handlePdfScroll, { passive: true });
    return () => panel.removeEventListener("scroll", handlePdfScroll);
  }, [handlePdfScroll]);

  // ── Click annotation card → scroll PDF to that region ─────────────
  const handleCardClick = useCallback((ann) => {
    setActiveAnnotation(ann);

    if (!pdfPanelRef.current || !imgRef.current || imgDimensions.height === 0) return;

    const bbox   = ann.bbox;
    if (!bbox) return;
    const annY   = (bbox.y || bbox.y0 || 0) * imgDimensions.height;
    const panelH = pdfPanelRef.current.clientHeight;

    isSyncingRef.current = true;
    pdfPanelRef.current.scrollTo({
      top:      annY - panelH * 0.3,
      behavior: "smooth",
    });
    setTimeout(() => { isSyncingRef.current = false; }, 500);
  }, [imgDimensions]);

  const scoreColor = (score) => {
    if (score >= 0.7) return { bg: "rgba(74,222,128,0.25)",  border: "#4ade80" };
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

        <div ref={marginBodyRef} style={styles.marginBody}>
          {pageAnnotations.length === 0 ? (
            <div style={styles.emptyState}>
              <div style={{ fontSize: "1.8rem", marginBottom: "10px", opacity: 0.4 }}>💬</div>
              <p style={styles.emptyText}>No feedback for this page.</p>
            </div>
          ) : (
            pageAnnotations.map((ann, i) => {
              const colors   = scoreColor(ann.score ?? ann.confidence);
              const isActive = activeAnnotation?.id === ann.id;
              return (
                <div
                  key={ann.id || i}
                  ref={el => { if (el) cardRefs.current[ann.id] = el; }}
                  onClick={() => handleCardClick(ann)}
                  style={{
                    ...styles.annotationCard,
                    borderLeft:  `3px solid ${colors.border}`,
                    background:  isActive ? colors.bg : "#fff",
                    boxShadow:   isActive ? `0 0 0 2px ${colors.border}` : "none",
                    transform:   isActive ? "translateX(3px)" : "none",
                    transition:  "all 0.2s",
                    cursor:      "pointer",
                  }}
                >
                  <div style={styles.annotationMeta}>
                    {ann.questionLabel && (
                      <span style={{
                        ...styles.regionBadge,
                        background: "#1a1a2e", color: "#fff",
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
                      color:      colors.border,
                      border:     `1px solid ${colors.border}`,
                    }}>
                      {Math.round((ann.score ?? ann.confidence) * 100)}%
                    </span>
                  </div>
                  <p style={styles.feedbackText}>{ann.feedback}</p>
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

        {/* Navigation */}
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

        {/* Scrollable page area */}
        <div ref={pdfPanelRef} style={styles.pageContainer}>

          {loadingPage && (
            <div style={styles.loadingOverlay}>
              <div style={{ color: "#9a9888", fontSize: "0.85rem" }}>Loading page…</div>
            </div>
          )}

          {!jobId && pdfFile && (
            <iframe
              src={URL.createObjectURL(pdfFile) + `#page=${currentPage}`}
              style={styles.iframe}
              title="PDF"
            />
          )}

          {pageImageUrl && (
            <div style={{ position: "relative", width: "100%" }}>
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

              {/* Annotation highlight overlays */}
              {/* MAP 1 — Colored highlight boxes on the text */}
              {imgDimensions.width > 0 && pageAnnotations.map((ann, i) => {
                const bbox   = ann.bbox;
                if (!bbox) return null;
                const colors   = scoreColor(ann.score ?? ann.confidence);
                const isActive = activeAnnotation?.id === ann.id;

                const left   = (bbox.x  || bbox.x0 || 0)   * imgDimensions.width;
                const top    = (bbox.y  || bbox.y0 || 0)    * imgDimensions.height;
                const width  = (bbox.width  || ((bbox.x1 || 0) - (bbox.x0 || 0)) || 0.9) * imgDimensions.width;
                const height = (bbox.height || ((bbox.y1 || 0) - (bbox.y0 || 0)) || 0.05) * imgDimensions.height;

                return (
                  <div
                    key={`highlight-${ann.id || i}`}
                    onClick={() => handleCardClick(ann)}
                    title={ann.feedback}
                    style={{
                      position:     "absolute",
                      left:         `${left}px`,
                      top:          `${top}px`,
                      width:        `${Math.max(width, 20)}px`,
                      height:       `${Math.max(height, 8)}px`,
                      background:   colors.bg,
                      border:       `${isActive ? 2 : 1}px solid ${colors.border}`,
                      borderRadius: "2px",
                      cursor:       "pointer",
                      opacity:      isActive ? 1 : 0.55,
                      transition:   "all 0.15s",
                      zIndex:       10,
                    }}
                  />
                );
              })}

              {/* MAP 2 — Score pills in left margin, no click handler */}
              {imgDimensions.width > 0 && pageAnnotations.map((ann, i) => {
                const bbox   = ann.bbox;
                if (!bbox) return null;
                const colors = scoreColor(ann.score ?? ann.confidence);
                const top    = (bbox.y || bbox.y0 || 0) * imgDimensions.height;

                return (
                  <div
                    key={`pill-${ann.id || i}`}
                    style={{
                      position:      "absolute",
                      left:          "-72px",
                      top:           `${top}px`,
                      transform:     "translateY(-25%)",
                      background:    "#fff",
                      border:        `2px solid ${colors.border}`,
                      borderRadius:  "6px",
                      padding:       "3px 7px",
                      whiteSpace:    "nowrap",
                      boxShadow:     "0 2px 6px rgba(0,0,0,0.10)",
                      display:       "flex",
                      flexDirection: "column",
                      alignItems:    "center",
                      minWidth:      "44px",
                      zIndex:        20,
                      pointerEvents: "none",
                    }}
                  >
                    {ann.questionLabel && (
                      <span style={{
                        fontSize:      "0.58rem",
                        fontWeight:    "700",
                        color:         "#1a1a2e",
                        fontFamily:    "monospace",
                        letterSpacing: "0.04em",
                        marginBottom:  "1px",
                      }}>
                        {ann.questionLabel}
                      </span>
                    )}
                    <span style={{
                      fontSize:   "0.85rem",
                      fontWeight: "800",
                      color:      colors.border,
                      fontFamily: "monospace",
                      lineHeight: "1.1",
                    }}>
                      {Math.round((ann.score ?? ann.confidence) * 100)}%
                    </span>
                    <div style={{
                      width:        "36px",
                      height:       "3px",
                      background:   "#e8e6de",
                      borderRadius: "99px",
                      marginTop:    "3px",
                      overflow:     "hidden",
                    }}>
                      <div style={{
                        width:        `${Math.round((ann.score ?? ann.confidence) * 100)}%`,
                        height:       "100%",
                        background:   colors.border,
                        borderRadius: "99px",
                      }} />
                    </div>
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

const styles = {
  wrapper: {
    display:       "flex",
    flexDirection: "row",
    width:         "100%",
    height:        "calc(100vh - 180px)",
    background:    "#f5f5f0",
    borderRadius:  "12px",
    overflow:      "hidden",
    border:        "1px solid #e0ddd6",
    marginTop:     "16px",
  },
  marginPanel: {
    width:         "280px",
    minWidth:      "280px",
    background:    "#fafaf7",
    borderRight:   "1px solid #e0ddd6",
    display:       "flex",
    flexDirection: "column",
    overflow:      "hidden",
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
    flex:      1,
    overflowY: "auto",
    padding:   "12px",
    scrollBehavior: "smooth",
  },
  emptyState: {
    display:        "flex",
    flexDirection:  "column",
    alignItems:     "center",
    justifyContent: "center",
    padding:        "40px 16px",
    textAlign:      "center",
  },
  emptyText: {
    fontSize:   "0.82rem",
    color:      "#6b6960",
    lineHeight: "1.5",
  },
  annotationCard: {
    background:   "#fff",
    border:       "1px solid #e8e6de",
    borderRadius: "8px",
    padding:      "10px 12px",
    marginBottom: "10px",
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
    padding:        "20px 20px 20px 80px",
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
    width:      "100%",
    height:     "auto",
    display:    "block",
    boxShadow:  "0 2px 12px rgba(0,0,0,0.15)",
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