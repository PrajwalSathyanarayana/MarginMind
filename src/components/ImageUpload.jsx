// import { useRef, useState, useCallback, useEffect } from 'react'

// export default function ImageUpload({ image, setImage }) {
//   const fileRef = useRef(null)
//   const videoRef = useRef(null)
//   const canvasRef = useRef(null)
//   const [cameraOpen, setCameraOpen] = useState(false)
//   const [stream, setStream] = useState(null)
//   const [cameraError, setCameraError] = useState(null)
//   const [dragover, setDragover] = useState(false)

//   const handleFile = (e) => {
//     const file = e.target.files?.[0]
//     if (!file) return
//     const reader = new FileReader()
//     reader.onload = (ev) => setImage(ev.target.result)
//     reader.readAsDataURL(file)
//   }

//   const handleDrop = (e) => {
//     e.preventDefault()
//     setDragover(false)
//     const file = e.dataTransfer.files?.[0]
//     if (!file || !file.type.startsWith('image/')) return
//     const reader = new FileReader()
//     reader.onload = (ev) => setImage(ev.target.result)
//     reader.readAsDataURL(file)
//   }

//   const openCamera = async () => {
//     setCameraOpen(true)
//     setCameraError(null)
//     try {
//       const mediaStream = await navigator.mediaDevices.getUserMedia({
//         video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } },
//         audio: false,
//       })
//       setStream(mediaStream)
//     } catch {
//       setCameraError('Could not access camera. Please check permissions and try again.')
//     }
//   }

//   useEffect(() => {
//     if (stream && videoRef.current) {
//       videoRef.current.srcObject = stream
//       videoRef.current.play()
//     }
//   }, [stream])

//   const closeCamera = useCallback(() => {
//     if (stream) {
//       stream.getTracks().forEach(t => t.stop())
//       setStream(null)
//     }
//     setCameraOpen(false)
//     setCameraError(null)
//   }, [stream])

//   const capturePhoto = () => {
//     if (!videoRef.current || !canvasRef.current) return
//     const video = videoRef.current
//     const canvas = canvasRef.current
//     canvas.width = video.videoWidth
//     canvas.height = video.videoHeight
//     const ctx = canvas.getContext('2d')
//     ctx.drawImage(video, 0, 0)
//     const dataUrl = canvas.toDataURL('image/jpeg', 0.92)
//     setImage(dataUrl)
//     closeCamera()
//   }

//   const removeImage = () => {
//     setImage(null)
//     if (fileRef.current) fileRef.current.value = ''
//   }

//   return (
//     <div className="section">
//       <div className="section-header">
//         <h2 className="section-title">Assignment</h2>
//         <p className="section-desc">Upload an image or use your camera</p>
//       </div>

//       <input
//         ref={fileRef}
//         type="file"
//         accept="image/*"
//         onChange={handleFile}
//         style={{ display: 'none' }}
//       />
//       <canvas ref={canvasRef} style={{ display: 'none' }} />

//       {!image ? (
//         <div
//           className={`upload-zone${dragover ? ' dragover' : ''}`}
//           onClick={() => fileRef.current?.click()}
//           onDragOver={(e) => { e.preventDefault(); setDragover(true) }}
//           onDragLeave={() => setDragover(false)}
//           onDrop={handleDrop}
//         >
//           <div className="upload-icon-wrap">
//             <svg viewBox="0 0 24 24">
//               <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
//               <polyline points="17 8 12 3 7 8" />
//               <line x1="12" y1="3" x2="12" y2="15" />
//             </svg>
//           </div>
//           <div className="upload-label">Drop image here or click to browse</div>
//           <div className="upload-sublabel">Supports JPG, PNG, HEIC</div>

//           <div className="upload-btns">
//             <button
//               className="btn btn-dark"
//               onClick={(e) => { e.stopPropagation(); fileRef.current?.click() }}
//             >
//               <svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
//               Upload
//             </button>
//             <button
//               className="btn btn-ghost"
//               onClick={(e) => { e.stopPropagation(); openCamera() }}
//             >
//               <svg viewBox="0 0 24 24"><path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z" /><circle cx="12" cy="13" r="4" /></svg>
//               Camera
//             </button>
//           </div>
//         </div>
//       ) : (
//         <div className="upload-zone has-image">
//           <div className="preview-wrap">
//             <img src={image} alt="Assignment" className="preview-img" />
//             <div className="preview-bar">
//               <button onClick={() => fileRef.current?.click()}>Replace</button>
//               <button className="danger" onClick={removeImage}>Remove</button>
//             </div>
//           </div>
//         </div>
//       )}

//       {/* Camera Modal */}
//       {cameraOpen && (
//         <div className="camera-modal" onClick={closeCamera}>
//           <div onClick={(e) => e.stopPropagation()}>
//             {cameraError ? (
//               <div className="camera-error">
//                 <p>{cameraError}</p>
//                 <button className="btn btn-ghost" style={{ color: '#fff', borderColor: 'rgba(255,255,255,0.2)' }} onClick={closeCamera}>
//                   Close
//                 </button>
//               </div>
//             ) : (
//               <>
//                 <video ref={videoRef} autoPlay playsInline muted />
//                 <div className="camera-controls">
//                   <button className="camera-close-btn" onClick={closeCamera}>Cancel</button>
//                   <button className="camera-capture-btn" onClick={capturePhoto} title="Capture" />
//                   <div style={{ width: 68 }} />
//                 </div>
//               </>
//             )}
//           </div>
//         </div>
//       )}
//     </div>
//   )
// }


import { useRef, useState } from 'react'

// Accepts a PDF file, sends it to the backend /upload endpoint,
// and returns the job result (job_id + annotations) to the parent
export default function PDFUpload({ onUploadComplete }) {
  const fileRef = useRef(null)
  const [dragover, setDragover] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)

  const handleFile = async (file) => {
    // Validate that the file is a PDF
    if (!file || file.type !== 'application/pdf') {
      setError('Please upload a PDF file.')
      return
    }

    setError(null)
    setUploading(true)

    try {
      // Build a multipart form request — same format as Swagger "Try it out"
      const formData = new FormData()
      formData.append('file', file)

      // Send to backend /upload endpoint
      const response = await fetch('http://127.0.0.1:8000/upload', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`)
      }

      const result = await response.json()

      // Pass the file object + backend result up to App.jsx
      // file object is needed to display the PDF locally in the viewer
      onUploadComplete(file, result)

    } catch (err) {
      setError(`Upload failed: ${err.message}`)
    } finally {
      setUploading(false)
    }
  }

  const handleInputChange = (e) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragover(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }

  return (
    <div className="section">
      <div className="section-header">
        <h2 className="section-title">Upload Assignment</h2>
        <p className="section-desc">Upload a PDF to get feedback</p>
      </div>

      {/* Hidden file input — PDF only */}
      <input
        ref={fileRef}
        type="file"
        accept="application/pdf"
        onChange={handleInputChange}
        style={{ display: 'none' }}
      />

      {/* Drop zone */}
      <div
        className={`upload-zone${dragover ? ' dragover' : ''}`}
        onClick={() => fileRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragover(true) }}
        onDragLeave={() => setDragover(false)}
        onDrop={handleDrop}
      >
        {uploading ? (
          // Uploading state
          <div className="loading-wrap">
            <div className="loader" />
            <div className="loading-label">Uploading and processing…</div>
          </div>
        ) : (
          // Default idle state
          <>
            <div className="upload-icon-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <div className="upload-label">Drop PDF here or click to browse</div>
            <div className="upload-sublabel">Supports PDF only</div>
            <div className="upload-btns">
              <button
                className="btn btn-dark"
                onClick={(e) => { e.stopPropagation(); fileRef.current?.click() }}
              >
                Upload PDF
              </button>
            </div>
          </>
        )}
      </div>

      {/* Error message */}
      {error && (
        <div style={{
          marginTop: '12px',
          padding: '10px 14px',
          background: '#3b1a1a',
          border: '1px solid #7f1d1d',
          borderRadius: '6px',
          color: '#f87171',
          fontSize: '0.85rem'
        }}>
          {error}
        </div>
      )}
    </div>
  )
}