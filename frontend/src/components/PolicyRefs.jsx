export default function PolicyRefs({ policies, citations }) {
  return (
    <div className="refs-card">
      {policies?.length > 0 && (
        <div className="ref-section">
          <span className="ref-label">Referenced Policies</span>
          <div className="ref-list">
            {policies.map(p => (
              <div key={p} className="ref-item">
                <span className="ref-dot" />{p}
              </div>
            ))}
          </div>
        </div>
      )}
      {citations?.length > 0 && (
        <div className="ref-section">
          <span className="ref-label">NIST Subcategories</span>
          <div className="citation-list">
            {citations.map(c => (
              <span key={c} className="citation-chip">{c}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}