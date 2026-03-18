import { useState } from "react"
import VerdictBanner   from "./VerdictBanner"
import RiskPanel       from "./RiskPanel"
import Recommendations from "./Recommendations"
import PolicyRefs      from "./PolicyRefs"

export default function ResultPanel({ result }) {
  const { query, query_type, interpretation,
          compliance, risk, recommendation,
          policy_references, warning } = result
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="result-layout">

      {/* Query echo */}
      <div className="query-row">
        <span className="query-label">Q</span>
        <span className="query-text">{query}</span>
      </div>

      {/* Row 1: Answer + Verdict — equal columns */}
      <div className="answer-verdict-row">
        <div className="answer-hero">
          <span className="answer-hero-label">Answer</span>
          <p className="answer-hero-text">{recommendation.summary}</p>
        </div>
        <VerdictBanner compliance={compliance} queryType={query_type} />
      </div>

      {/* Row 2: Policy context — 2 line preview, expand on click */}
      <div className="card policy-card">
        <div className="policy-header" onClick={() => setExpanded(!expanded)}>
          <span className="card-label" style={{ marginBottom:0 }}>Policy Context</span>
          <span className="expand-toggle">{expanded ? "▲ Show less" : "▼ Show more"}</span>
        </div>
        {/* Always visible: 2-line preview */}
        <p className={`card-body policy-preview ${expanded ? "policy-full" : ""}`}>
          {interpretation}
        </p>
      </div>

      {/* Row 3: Risk + Steps */}
      <div className="grid-2">
        <RiskPanel risk={risk} />
        <Recommendations rec={recommendation} queryType={query_type} />
      </div>

      {/* Row 4: Policy refs */}
      <PolicyRefs policies={policy_references} citations={compliance.citations} />

      {warning && <div className="warning-box">⚠ {warning}</div>}
    </div>
  )
}