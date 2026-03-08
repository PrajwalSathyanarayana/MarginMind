// import { useRef, useState } from 'react'

// export default function RubricEditor({ rubrics, setRubrics }) {
//   const pdfRef = useRef(null)
//   const [pdfName, setPdfName] = useState(null)

//   const add = () => setRubrics([...rubrics, { id: Date.now(), name: '', points: '' }])

//   const update = (id, field, value) =>
//     setRubrics(rubrics.map(r => (r.id === id ? { ...r, [field]: value } : r)))

//   const remove = (id) => setRubrics(rubrics.filter(r => r.id !== id))

//   const total = rubrics.reduce((s, r) => s + (Number(r.points) || 0), 0)

//   const handlePdf = async (e) => {
//     const file = e.target.files?.[0]
//     if (!file) return
//     setPdfName(file.name)

//     // Read PDF as text — extract lines that look like rubric criteria
//     const text = await file.text()
//     // Simple heuristic: split by newlines, find lines with numbers (points)
//     const lines = text.split(/\n|\r/).map(l => l.trim()).filter(l => l.length > 3)
//     const parsed = []
//     for (const line of lines) {
//       // Match patterns like "Content Accuracy - 30" or "Content Accuracy (30 pts)" or "30 Content Accuracy"
//       const match = line.match(/^(.+?)\s*[-–—:]\s*(\d+)\s*(?:pts?|points?|marks?)?\s*$/i)
//         || line.match(/^(.+?)\s*\(?\s*(\d+)\s*(?:pts?|points?|marks?)?\s*\)?\s*$/i)
//         || line.match(/^(\d+)\s*[-–—:]?\s*(.+)$/)
//       if (match) {
//         let name = match[1].trim()
//         let pts = match[2].trim()
//         // If first capture is number, swap
//         if (/^\d+$/.test(name)) {
//           [name, pts] = [pts, name]
//         }
//         if (name && pts && Number(pts) > 0) {
//           parsed.push({ id: Date.now() + parsed.length, name, points: pts })
//         }
//       }
//     }
//     if (parsed.length > 0) {
//       setRubrics(parsed)
//     }
//   }

//   const clearPdf = () => {
//     setPdfName(null)
//     if (pdfRef.current) pdfRef.current.value = ''
//   }

//   return (
//     <div className="section">
//       <div className="section-header">
//         <div className="section-header-row">
//           <div>
//             <h2 className="section-title">Rubrics</h2>
//             <p className="section-desc">Define criteria and point values</p>
//           </div>
//           <input
//             ref={pdfRef}
//             type="file"
//             accept=".pdf,.txt,.csv"
//             onChange={handlePdf}
//             style={{ display: 'none' }}
//           />
//           <button className="btn btn-ghost btn-sm" onClick={() => pdfRef.current?.click()}>
//             <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" /></svg>
//             Upload Rubric
//           </button>
//         </div>
//         {pdfName && (
//           <div className="pdf-badge">
//             <span>{pdfName}</span>
//             <button onClick={clearPdf}>&times;</button>
//           </div>
//         )}
//       </div>

//       <div className="rubric-list">
//         {rubrics.map((r, i) => (
//           <div key={r.id} className="rubric-row">
//             <div className="rubric-index">{i + 1}</div>
//             <input
//               className="name-input"
//               type="text"
//               placeholder="Criterion name"
//               value={r.name}
//               onChange={(e) => update(r.id, 'name', e.target.value)}
//             />
//             <input
//               className="pts-input"
//               type="number"
//               placeholder="Pts"
//               min="0"
//               value={r.points}
//               onChange={(e) => update(r.id, 'points', e.target.value)}
//             />
//             <button className="rubric-del" onClick={() => remove(r.id)} title="Remove">
//               <svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
//             </button>
//           </div>
//         ))}
//       </div>

//       <button className="add-rubric" onClick={add}>+ Add criterion</button>

//       {rubrics.length > 0 && (
//         <div className="rubric-total">
//           Total <strong>{total} pts</strong>
//         </div>
//       )}
//     </div>
//   )
// }
