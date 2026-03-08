// export default function Results({ results, onReset }) {
//   const { totalScore, maxScore, rubricScores, feedback } = results
//   const pct = maxScore > 0 ? Math.round((totalScore / maxScore) * 100) : 0

//   const grade = (p) => {
//     if (p >= 90) return { letter: 'A', label: 'Excellent', cls: 'excellent' }
//     if (p >= 75) return { letter: 'B', label: 'Good', cls: 'good' }
//     if (p >= 60) return { letter: 'C', label: 'Average', cls: 'average' }
//     return { letter: 'F', label: 'Needs Work', cls: 'poor' }
//   }

//   const g = grade(pct)
//   const circumference = 2 * Math.PI * 56 // r=56
//   const offset = circumference - (pct / 100) * circumference

//   const rowLevel = (scored, max) => {
//     const p = max > 0 ? scored / max : 0
//     if (p >= 0.8) return 'high'
//     if (p >= 0.6) return 'mid'
//     return 'low'
//   }

//   return (
//     <div className="section results-card">
//       <div className="section-header">
//         <h2 className="section-title">Results</h2>
//         <p className="section-desc">Grading breakdown for this assignment</p>
//       </div>

//       <div className="score-hero">
//         <div className={`score-ring ${g.cls}`}>
//           <svg viewBox="0 0 120 120">
//             <circle className="ring-bg" />
//             <circle
//               className="ring-fill"
//               style={{ strokeDashoffset: offset }}
//             />
//           </svg>
//           <div className="score-pct">{pct}%</div>
//           <div className="score-tag">{g.label}</div>
//         </div>
//         <div className="score-summary">
//           <strong>{totalScore}</strong> / {maxScore} points &mdash; Grade <strong>{g.letter}</strong>
//         </div>
//       </div>

//       <div className="result-breakdown">
//         {rubricScores.map((item, i) => {
//           const level = rowLevel(item.scored, item.max)
//           const barPct = item.max > 0 ? (item.scored / item.max) * 100 : 0
//           return (
//             <div key={i} className={`result-row ${level}`}>
//               <div className="result-row-left">
//                 <div className="result-dot" />
//                 <span className="result-row-name">{item.name}</span>
//               </div>
//               <div className="result-bar-wrap">
//                 <div className="result-bar" style={{ width: `${barPct}%` }} />
//               </div>
//               <span className="result-row-score">{item.scored}/{item.max}</span>
//             </div>
//           )
//         })}
//       </div>

//       {feedback && (
//         <div className="feedback-box">
//           <h4>Feedback</h4>
//           <p>{feedback}</p>
//         </div>
//       )}

//       <div className="actions">
//         <button className="btn btn-ghost" onClick={onReset}>Grade Another</button>
//         <button className="btn btn-dark" onClick={() => window.print()}>Export</button>
//       </div>
//     </div>
//   )
// }
