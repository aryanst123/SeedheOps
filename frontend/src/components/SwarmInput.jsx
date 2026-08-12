import { Mic, Send } from 'lucide-react'

/** Mock voice/text input bar for triggering the swarm */
export default function SwarmInput({ value, onChange, onProcess, isProcessing, disabled }) {
  return (
    <div className="swarm-input-wrap">
      <div className="swarm-input-bar">
        <Mic size={18} className="swarm-input-bar__icon" />
        <input
          type="text"
          className="swarm-input-bar__field"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Paste telemetry alerts, stack traces, or incident logs…"
          disabled={isProcessing || disabled}
        />
        <button
          type="button"
          className="swarm-input-bar__btn"
          onClick={onProcess}
          disabled={isProcessing || disabled || !value.trim()}
        >
          <Send size={14} />
          {isProcessing ? 'Triaging…' : 'Execute Triage'}
        </button>
      </div>
      <p className="swarm-input-hint">
        Type or paste your telemetry alert, then hit Execute Triage — DevOps swarm agents activate sequentially.
      </p>
    </div>
  )
}
