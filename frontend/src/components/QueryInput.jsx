import { useState } from "react"

export default function QueryInput({ onSubmit, loading, compact }) {
  const [value, setValue] = useState("")

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      onSubmit(value)
      if (compact) setValue("")
    }
  }

  function handleSubmit() {
    onSubmit(value)
    if (compact) setValue("")
  }

  return (
    <div className={`input-wrap ${compact ? "input-compact" : ""}`}>
      <textarea
        className="query-input"
        rows={compact ? 1 : 2}
        placeholder={compact
          ? "Ask another question…"
          : "e.g. Can I share customer data with another team?"}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKey}
        disabled={loading}
      />
      <button
        className="submit-btn"
        onClick={handleSubmit}
        disabled={loading || !value.trim()}
      >
        {loading ? "Analysing…" : "Ask"}
      </button>
    </div>
  )
}