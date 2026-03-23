import { useState } from 'react'

export default function ParsedContent({ parsed = { pages: [], tables: [], figures: [] } }) {
  const pages = parsed.pages || []
  const tables = parsed.tables || []
  const figures = parsed.figures || []
  const [selectedPage, setSelectedPage] = useState(1)

  const maxPage = Math.max(1, pages.length)
  const currentPage = Math.min(selectedPage, maxPage)

  const pageText = (pages.find(p => p.page_num === currentPage)?.text || '').trim()
  const pageTables = tables.filter(t => t.page_num === currentPage)
  const pageFigures = figures.filter(f => f.page_num === currentPage)

  return (
    <div className="section parsed-section">
      <div className="section-header parsed-header">
        <div>
          <h2 className="section-title">Parsed Content</h2>
          <p className="section-desc">Text, tables, and figure/diagram regions extracted from upload</p>
        </div>
        <div className="parsed-stats">
          <span>{pages.length} page{pages.length !== 1 ? 's' : ''}</span>
          <span>{tables.length} table{tables.length !== 1 ? 's' : ''}</span>
          <span>{figures.length} figure{figures.length !== 1 ? 's' : ''}</span>
        </div>
      </div>

      <div className="parsed-page-nav">
        <button
          className="btn btn-ghost"
          onClick={() => setSelectedPage(p => Math.max(1, p - 1))}
          disabled={currentPage <= 1}
        >
          Prev Page
        </button>
        <span className="parsed-page-label">Page {currentPage} of {maxPage}</span>
        <button
          className="btn btn-ghost"
          onClick={() => setSelectedPage(p => Math.min(maxPage, p + 1))}
          disabled={currentPage >= maxPage}
        >
          Next Page
        </button>
      </div>

      <div className="parsed-grid">
        <div className="parsed-card">
          <h3>Text</h3>
          {pageText ? (
            <pre className="parsed-text">{pageText}</pre>
          ) : (
            <p className="parsed-empty">No readable text detected on this page.</p>
          )}
        </div>

        <div className="parsed-card">
          <h3>Tables</h3>
          {pageTables.length === 0 && <p className="parsed-empty">No tables detected on this page.</p>}
          {pageTables.map((table, index) => (
            <div className="parsed-table-wrap" key={`${currentPage}-${index}`}>
              <div className="parsed-table-label">Table {index + 1}</div>
              <table className="parsed-table">
                <tbody>
                  {(table.data || []).map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {(row || []).map((cell, cellIndex) => (
                        <td key={cellIndex}>{cell ?? ''}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>

        <div className="parsed-card">
          <h3>Figures / Diagrams</h3>
          {pageFigures.length === 0 && <p className="parsed-empty">No figure regions detected on this page.</p>}
          {pageFigures.map((figure) => (
            <div className="parsed-figure-row" key={figure.id}>
              <div className="parsed-figure-title">{figure.id}</div>
              <div className="parsed-figure-meta">
                source: {figure.source || 'unknown'} | size: {figure.width}x{figure.height}
              </div>
              {figure.bbox && (
                <div className="parsed-figure-meta">
                  bbox: ({figure.bbox.x0}, {figure.bbox.y0}) to ({figure.bbox.x1}, {figure.bbox.y1})
                </div>
              )}
              {figure.preview_data_url ? (
                <img
                  src={figure.preview_data_url}
                  alt={figure.id}
                  className="parsed-figure-preview"
                />
              ) : (
                <div className="parsed-figure-meta">Preview unavailable for this figure.</div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
