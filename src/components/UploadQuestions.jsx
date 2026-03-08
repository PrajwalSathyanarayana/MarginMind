import { useRef, useState } from 'react'

export default function UploadQuestions({ file, setFile }) {
  const fileRef = useRef(null)
  const [dragover, setDragover] = useState(false)

  const handleFile = (f) => {
    if (!f) return
    setFile(f)
  }

  const handleInput = (e) => handleFile(e.target.files?.[0])

  const handleDrop = (e) => {
    e.preventDefault()
    setDragover(false)
    handleFile(e.dataTransfer.files?.[0])
  }

  const remove = () => {
    setFile(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  const icon = (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" width="20" height="20">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  )

  return (
    <div className="section">
      <div className="section-header">
        <h2 className="section-title">Questions</h2>
        <p className="section-desc">Upload the question paper (PDF, image, or text file)</p>
      </div>

      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.txt,.csv,.doc,.docx,image/*"
        onChange={handleInput}
        style={{ display: 'none' }}
      />

      {!file ? (
        <div
          className={`upload-zone${dragover ? ' dragover' : ''}`}
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragover(true) }}
          onDragLeave={() => setDragover(false)}
          onDrop={handleDrop}
        >
          <div className="upload-icon-wrap">
            {icon}
          </div>
          <div className="upload-label">Drop question paper here or click to browse</div>
          <div className="upload-sublabel">PDF, DOCX, TXT, or image</div>
          <div className="upload-btns">
            <button
              className="btn btn-dark"
              onClick={(e) => { e.stopPropagation(); fileRef.current?.click() }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" width="14" height="14">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              Browse File
            </button>
          </div>
        </div>
      ) : (
        <div className="file-preview">
          <div className="file-preview-icon">{icon}</div>
          <div className="file-preview-info">
            <div className="file-preview-name">{file.name}</div>
            <div className="file-preview-meta">
              {(file.size / 1024).toFixed(0)} KB &middot; {file.type || 'unknown type'}
            </div>
          </div>
          <div className="file-preview-actions">
            <button className="btn btn-ghost btn-sm" onClick={() => fileRef.current?.click()}>
              Replace
            </button>
            <button className="rubric-del" onClick={remove}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" width="14" height="14">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
