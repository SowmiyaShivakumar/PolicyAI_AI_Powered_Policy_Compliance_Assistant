export default function Recommendations({ rec, queryType }) {
  const { steps, escalate, escalate_to, summary } = rec
  const urgent = queryType === "INCIDENT"

  function cleanStep(text) {
    // Remove "step N:" prefix if LLM added it
    const cleaned = text.replace(/^step\s*\d+\s*[:—\-]\s*/i, "").trim()
    // Capitalize first letter of sentence
    return cleaned.charAt(0).toUpperCase() + cleaned.slice(1)
  }

  return (
    <div className="card">
      <span className="card-label">{urgent ? "Immediate Actions" : "Recommendations"}</span>
      <p className="rec-summary">{summary}</p>
      <ol className="steps">
        {steps.map((s, i) => (
          <li key={i} className={`step ${urgent ? "step-urgent" : ""}`}>
            <span className="step-num">STEP {i + 1}</span>
            <span className="step-text">{cleanStep(s)}</span>
          </li>
        ))}
      </ol>
      {escalate && (
        <div className="escalate-box">
          <span className="escalate-icon">↑</span>
          <div>
            <div className="escalate-title">Escalation Required</div>
            {escalate_to && (
              <div className="escalate-to">Contact: <strong>{escalate_to}</strong></div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}