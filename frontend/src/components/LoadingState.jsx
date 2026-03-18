import { useState, useEffect } from "react"

const STEPS = [
  { id: 1, label: "Searching policy database",    sub: "Milvus vector + BM25 search" },
  { id: 2, label: "Traversing knowledge graph",   sub: "Neo4j NIST CSF traversal"    },
  { id: 3, label: "Analysing compliance",          sub: "Checking policy rules"        },
  { id: 4, label: "Generating recommendation",     sub: "Building your response"       },
]

export default function LoadingState() {
  const [active, setActive] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setActive(prev => (prev < STEPS.length - 1 ? prev + 1 : prev))
    }, 1400)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="loading-wrap">
      {/* Dot-ring spinner */}
      <div className="dot-ring">
        {Array.from({ length: 8 }).map((_, i) => (
          <span key={i} className="dot-ring-dot" style={{ "--i": i }} />
        ))}
      </div>

      {/* Sequential steps */}
      <div className="loading-steps">
        {STEPS.map((step, i) => {
          const done    = i < active
          const current = i === active
          return (
            <div key={step.id}
              className={`load-step ${done ? "done" : ""} ${current ? "current" : ""}`}>
              <div className="load-step-icon">
                {done    ? "✓" : ""}
                {current ? <span className="step-pulse" /> : ""}
                {!done && !current ? "" : ""}
              </div>
              <div className="load-step-text">
                <span className="load-step-label">{step.label}</span>
                <span className="load-step-sub">{step.sub}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}