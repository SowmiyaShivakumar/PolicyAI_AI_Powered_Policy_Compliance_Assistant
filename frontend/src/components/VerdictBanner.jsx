const CONFIG = {
  COMPLIANT:       { label:"Compliant",      icon:"✓", cls:"green"  },
  NEEDS_REVIEW:    { label:"Needs Review",   icon:"⚠", cls:"amber"  },
  NON_COMPLIANT:   { label:"Non-Compliant",  icon:"✕", cls:"red"    },
  REQUIRES_ACTION: { label:"Action Required",icon:"!", cls:"urgent" },
  INFO:            { label:"Information",    icon:"i", cls:"blue"   },
}

export default function VerdictBanner({ compliance, queryType }) {
  const { verdict, score, reason, citations } = compliance
  const cfg = CONFIG[verdict] || CONFIG.INFO

  return (
    <div className={`verdict-card verdict-${cfg.cls}`}>
      <span className="card-label">Compliance Verdict</span>
      <div className="verdict-top">
        <div className="verdict-icon">{cfg.icon}</div>
        <div className="verdict-name">{cfg.label}</div>
      </div>
      <p className="verdict-reason">{reason}</p>
      {score != null && (
        <div className="score-row">
          <div className="score-bar-wrap">
            <div className="score-bar" style={{ width:`${score}%` }} />
          </div>
          <span className="score-val">{score}/100</span>
        </div>
      )}
      {citations?.length > 0 && (
        <div className="citations">
          {citations.map(c => <span key={c} className="citation-tag">{c}</span>)}
        </div>
      )}
    </div>
  )
}