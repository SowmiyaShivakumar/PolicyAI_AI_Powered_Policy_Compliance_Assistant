import { useState } from "react"
import QueryInput   from "./components/QueryInput"
import ResultPanel  from "./components/ResultPanel"
import LoadingState from "./components/LoadingState"

const EXAMPLES = [
  "Can I share customer data with another team?",
  "Who is responsible for cybersecurity risk objectives?",
  "If I accidentally see data not belonging to my project, should I report it?",
  "Can I work remotely while travelling abroad?",
]

export default function App() {
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  const hasResult = result || loading || error

  async function handleSubmit(q) {
    if (!q.trim()) return
    setLoading(true); setError(null); setResult(null)
    window.scrollTo({ top: 0, behavior: "smooth" })
    try {
      const res  = await fetch("/api/v1/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, top_k: 5 }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Something went wrong")
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo" onClick={() => { setResult(null); setError(null); }}>
            <div className="logo-icon">⚖</div>
            <div>
              <div className="logo-title">PolicyAI</div>
              <div className="logo-sub">NIST CSF 2.0</div>
            </div>
          </div>
          {hasResult
            ? <button className="new-query-btn" onClick={() => { setResult(null); setError(null); }}>← New question</button>
            : <div className="header-badge">Powered by NIST CSF 2.0</div>
          }
        </div>
      </header>

      <main className="main">
        {!hasResult && (
          <>
            <div className="hero">
              <h1>Ask anything about your<br /><span className="accent">company policies</span></h1>
              <p className="hero-sub">Instant compliance guidance grounded in NIST CSF 2.0.</p>
            </div>
            <QueryInput onSubmit={handleSubmit} loading={loading} />
            <div className="examples">
              <span className="examples-label">Try asking</span>
              <div className="example-pills">
                {EXAMPLES.map(q => (
                  <button key={q} className="pill" onClick={() => handleSubmit(q)}>{q}</button>
                ))}
              </div>
            </div>
          </>
        )}

        {loading && <LoadingState />}
        {error && !loading && <div className="error-box">⚠ {error}</div>}

        {result && !loading && (
          <div style={{ display:"flex", flexDirection:"column", gap:14 }}>
            <QueryInput onSubmit={handleSubmit} loading={loading} compact />
            <ResultPanel result={result} />
          </div>
        )}
      </main>
    </div>
  )
}