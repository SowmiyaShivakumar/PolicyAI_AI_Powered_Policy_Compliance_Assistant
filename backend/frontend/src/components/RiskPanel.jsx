const CLS = { LOW:"risk-low", MEDIUM:"risk-medium", HIGH:"risk-high", CRITICAL:"risk-critical" }

export default function RiskPanel({ risk }) {
  const { level, reason, affected, potential_impact } = risk
  return (
    <div className="card">
      <span className="card-label">Risk Assessment</span>
      <div className={`risk-badge ${CLS[level]||"risk-low"}`}>{level}</div>
      <p className="card-body">{reason}</p>
      {affected?.length > 0 && (
        <>
          <span className="affected-label">Affected Functions</span>
          <div className="affected-pills">
            {affected.map(fn => <span key={fn} className="fn-pill">{fn}</span>)}
          </div>
        </>
      )}
      {/* {potential_impact && (
        <div className="impact">
          <span className="impact-label">Impact</span>
          <p className="impact-text">{potential_impact}</p>
        </div>
      )} */}
    </div>
  )
}