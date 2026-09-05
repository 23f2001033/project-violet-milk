/**
 * Shared UI primitives. Kept deliberately small - organs compose these rather
 * than inventing their own chrome, so the whole workspace reads as one system.
 */

import { riskColor } from '../api'

export function Panel({ title, right, children, className = '' }) {
  return (
    <section className={`organ flex flex-col min-h-0 ${className}`}>
      {(title || right) && (
        <header className="flex items-center gap-3 px-4 py-2.5 border-b border-edge shrink-0">
          <h2 className="label">{title}</h2>
          <div className="ml-auto flex items-center gap-2">{right}</div>
        </header>
      )}
      <div className="min-h-0 flex-1">{children}</div>
    </section>
  )
}

export function RiskPill({ level, score, className = '' }) {
  const c = riskColor(level)
  return (
    <span
      className={`font-mono text-[11px] font-bold px-2 py-0.5 rounded whitespace-nowrap ${className}`}
      style={{ color: c, background: `${c}1f`, border: `1px solid ${c}44` }}
    >
      {score} · {level}
    </span>
  )
}

/**
 * Confirmed vs inferred is the most important distinction in the product.
 * It gets its own visual treatment everywhere it appears - never collapsed
 * into a single "verified" state.
 */
export function ConfidenceTag({ value }) {
  const inferred = value === 'inferred'
  const unknown = value === 'unknown'
  const color = inferred ? '#d9b21c' : unknown ? '#6b6579' : '#3d9a6d'
  return (
    <span
      className="font-mono text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded"
      style={{ color, background: `${color}1a` }}
    >
      {inferred ? '◌ inferred' : unknown ? '· unknown' : '✓ confirmed'}
    </span>
  )
}

export function Stat({ label, value, accent, mono = true }) {
  return (
    <div className="px-4 py-2.5 border-r border-edge last:border-r-0 min-w-0">
      <div className="label">{label}</div>
      <div
        className={`${mono ? 'font-mono' : ''} text-sm mt-0.5 truncate`}
        style={accent ? { color: accent } : undefined}
        title={String(value)}
      >
        {value}
      </div>
    </div>
  )
}

export function Button({ children, variant = 'ghost', className = '', ...rest }) {
  const styles = {
    primary:
      'bg-violet/20 border-violet/60 text-violet-200 hover:bg-violet/30',
    ghost:
      'bg-panel2 border-edge text-slate-300 hover:border-slate-600 hover:text-slate-100',
    danger:
      'bg-risk-critical/15 border-risk-critical/50 text-risk-critical hover:bg-risk-critical/25',
  }[variant]
  return (
    <button
      className={`px-3 py-1.5 text-xs font-medium rounded border transition-colors
                  disabled:opacity-40 disabled:cursor-not-allowed ${styles} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}

export function Empty({ children }) {
  return (
    <div className="p-8 text-center text-xs text-slate-600">{children}</div>
  )
}

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="p-8 text-center font-mono text-xs text-slate-600">{label}</div>
  )
}

export function ErrorBox({ error, onRetry }) {
  return (
    <div className="p-6 text-center space-y-3">
      <p className="text-xs text-risk-critical font-mono">{String(error)}</p>
      {onRetry && <Button onClick={onRetry}>Retry</Button>}
    </div>
  )
}

/** Truncate a hash or address for display without losing identifiability. */
export const short = (s, head = 10, tail = 6) =>
  !s ? '—' : s.length <= head + tail + 1 ? s : `${s.slice(0, head)}…${s.slice(-tail)}`

export const timeIST = (iso) =>
  new Date(iso).toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: 'Asia/Kolkata',
  })

export const dateIST = (iso) =>
  new Date(iso).toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'Asia/Kolkata',
  })

export const delta = (secs) => {
  if (!secs) return null
  if (secs < 60) return `+${secs}s`
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return s ? `+${m}m ${s}s` : `+${m}m`
}
