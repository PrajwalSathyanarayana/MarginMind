import { useEffect, useRef, useState } from 'react'

// Displays a PDF page by page with a left margin panel for comments/feedback
// pdfFile     — the raw File object from the upload
// annotations — list of feedback items from the backend
export default function PDFViewer({ pdfFile, annotations = [] }) {
  const [pdfUrl, setPdfUrl] = useState(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const iframeRef = useRef(null)

  // Convert the File object into a local URL the browser can display
  useEffect(() => {
    if (!pdfFile) return
    const url = URL.createObjectURL(pdfFile)
    setPdfUrl(url)

    // Cleanup the object URL when component unmounts to avoid memory leaks
    return () => URL.revokeObjectURL(url)
  }, [pdfFile])

  // Filter annotations to only show those for the current page
  const pageAnnotations = annotations.filter(a => a.page === currentPage)

  return (
    <div style={styles.wrapper}>

      {/* ── LEFT MARGIN PANEL ─────────────────────────────────── */}
      {/* This is the white space extension on the left side       */}
      {/* Comments and feedback appear here, anchored to the page  */}
      <div style={styles.marginPanel}>

        <div style={styles.marginHeader}>
          <span style={styles.marginTitle}>Feedback</span>
          <span style={styles.marginPage}>Page {currentPage}</span>
        </div>

        {pageAnnotations.length === 0 ? (
          // Empty state — will be replaced by real Gemini feedback in M2
          <div style={styles.emptyState}>
            <div style={styles.emptyIcon}>💬</div>
            <p style={styles.emptyText}>
              No feedback yet for this page.
            </p>
            <p style={styles.emptySubtext}>
              Gemini-generated comments will appear here in Milestone 2.
            </p>
          </div>
        ) : (
          // Render each annotation as a comment card
          <div style={styles.annotationList}>
            {pageAnnotations.map((annotation, i) => (
              <div key={annotation.id || i} style={styles.annotationCard}>

                {/* Confidence badge */}
                <div style={styles.annotationMeta}>
                  <span style={styles.regionType}>
                    {annotation.region_type}
                  </span>
                  <span style={{
                    ...styles.confidenceBadge,
                    background: annotation.confidence > 0.8
                      ? '#1a2e1a' : '#3b2a10',
                    color: annotation.confidence > 0.8
                      ? '#4ade80' : '#fbbf24',
                  }}>
                    {Math.round(annotation.confidence * 100)}% confidence
                  </span>
                </div>

                {/* Feedback text */}
                <p style={styles.feedbackText}>{annotation.feedback}</p>

                {/* Needs review flag */}
                {annotation.needs_review && (
                  <div style={styles.reviewFlag}>
                    ⚠ Needs Review
                  </div>
                )}

              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── PDF DISPLAY AREA ──────────────────────────────────── */}
      <div style={styles.pdfPanel}>

        {/* Page navigation bar */}
        <div style={styles.navBar}>
          <button
            style={styles.navBtn}
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1}
          >
            ← Prev
          </button>
          <span style={styles.pageIndicator}>
            Page {currentPage} of {totalPages}
          </span>
          <button
            style={styles.navBtn}
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
          >
            Next →
          </button>
        </div>

        {/* PDF rendered via browser's built-in PDF viewer */}
        {pdfUrl && (
          <iframe
            ref={iframeRef}
            src={`${pdfUrl}#page=${currentPage}`}
            style={styles.iframe}
            title="PDF Viewer"
            onLoad={() => {
              // Try to detect total pages from the PDF object
              // Falls back to 1 if browser doesn't expose this
              try {
                const doc = iframeRef.current?.contentWindow?.PDFViewerApplication?.pdfDocument
                if (doc) setTotalPages(doc.numPages)
              } catch {
                // Cross-origin iframe restriction — page count stays at 1
                // Will be replaced with proper PDF.js in M2
              }
            }}
          />
        )}
      </div>

    </div>
  )
}

// ── STYLES ────────────────────────────────────────────────────────────────────
const styles = {
  wrapper: {
    display: 'flex',
    flexDirection: 'row',
    width: '100%',
    height: 'calc(100vh - 180px)', // fills the screen minus header
    background: '#f5f5f0',
    borderRadius: '12px',
    overflow: 'hidden',
    border: '1px solid #e0ddd6',
    marginTop: '16px',
  },

  // Left margin panel
  marginPanel: {
    width: '280px',
    minWidth: '280px',
    background: '#fafaf7',
    borderRight: '1px solid #e0ddd6',
    display: 'flex',
    flexDirection: 'column',
    overflowY: 'auto',
  },

  marginHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '14px 16px',
    borderBottom: '1px solid #e0ddd6',
    background: '#f0efe9',
    position: 'sticky',
    top: 0,
    zIndex: 1,
  },

  marginTitle: {
    fontSize: '0.8rem',
    fontWeight: '700',
    color: '#3d3b30',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
  },

  marginPage: {
    fontSize: '0.72rem',
    color: '#9a9888',
    fontFamily: 'monospace',
  },

  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '40px 20px',
    textAlign: 'center',
    flex: 1,
  },

  emptyIcon: {
    fontSize: '2rem',
    marginBottom: '12px',
    opacity: 0.4,
  },

  emptyText: {
    fontSize: '0.82rem',
    color: '#6b6960',
    marginBottom: '6px',
    lineHeight: '1.5',
  },

  emptySubtext: {
    fontSize: '0.72rem',
    color: '#9a9888',
    lineHeight: '1.5',
  },

  annotationList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    padding: '14px',
    overflowY: 'auto',
  },

  annotationCard: {
    background: '#fff',
    border: '1px solid #e8e6de',
    borderRadius: '8px',
    padding: '12px',
    borderLeft: '3px solid #7c5cfc',
  },

  annotationMeta: {
    display: 'flex',
    gap: '6px',
    marginBottom: '8px',
    flexWrap: 'wrap',
  },

  regionType: {
    fontSize: '0.62rem',
    padding: '2px 7px',
    borderRadius: '4px',
    background: '#ede9fe',
    color: '#5b21b6',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },

  confidenceBadge: {
    fontSize: '0.62rem',
    padding: '2px 7px',
    borderRadius: '4px',
    fontWeight: '600',
  },

  feedbackText: {
    fontSize: '0.8rem',
    color: '#3d3b30',
    lineHeight: '1.6',
    margin: '0',
  },

  reviewFlag: {
    marginTop: '8px',
    fontSize: '0.72rem',
    color: '#b45309',
    background: '#fef3c7',
    border: '1px solid #fde68a',
    borderRadius: '4px',
    padding: '3px 8px',
    display: 'inline-block',
  },

  // Right PDF display — takes all remaining space
  pdfPanel: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    background: '#e8e6df',
    minWidth: 0, // prevents flex overflow
  },

  navBar: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '16px',
    padding: '10px 16px',
    background: '#f0efe9',
    borderBottom: '1px solid #e0ddd6',
    flexShrink: 0,
  },

  navBtn: {
    background: '#fff',
    border: '1px solid #d0cec6',
    borderRadius: '6px',
    padding: '5px 14px',
    fontSize: '0.8rem',
    cursor: 'pointer',
    color: '#3d3b30',
  },

  pageIndicator: {
    fontSize: '0.8rem',
    color: '#6b6960',
    fontFamily: 'monospace',
  },

  // iframe fills all remaining height
  iframe: {
    flex: 1,
    width: '100%',
    height: '100%',
    border: 'none',
    display: 'block',
  },
}