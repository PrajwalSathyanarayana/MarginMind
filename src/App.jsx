import { useState } from 'react'
import './App.css'
import ImageUpload from './components/ImageUpload'
import UploadQuestions from './components/UploadQuestions'

function App() {
  const [image, setImage] = useState(null)
  const [questionsFile, setQuestionsFile] = useState(null)
  const [loading, setLoading] = useState(false)

  const step = loading ? 3 : questionsFile ? 2 : image ? 2 : 1
  const canGrade = image && questionsFile

  const handleGrade = () => {
    if (!canGrade) return
    setLoading(true)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Grader</h1>
        <p>Upload assignment and questions to grade.</p>
      </header>

      <div className="steps">
        {['Assignment', 'Questions', 'Grading'].map((label, i) => {
          const n = i + 1
          const cls = n < step ? 'completed' : n === step ? 'active' : ''
          return (
            <div key={label} className={`step ${cls}`}>
              <span className="step-label">{label}</span>
            </div>
          )
        })}
      </div>

      {loading ? (
        <div className="section">
          <div className="loading-wrap">
            <div className="loader" />
            <div className="loading-label">Analyzing assignment…</div>
          </div>
        </div>
      ) : (
        <>
          <ImageUpload image={image} setImage={setImage} />
          <UploadQuestions file={questionsFile} setFile={setQuestionsFile} />

          <button
            className="grade-btn"
            disabled={!canGrade}
            onClick={handleGrade}
          >
            {canGrade ? 'Grade Assignment' : 'Upload assignment & questions to grade'}
          </button>
        </>
      )}
    </div>
  )
}

export default App
