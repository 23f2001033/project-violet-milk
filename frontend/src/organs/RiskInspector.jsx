/**
 * ORGAN 5 — Risk Inspector ("Why is this utensil violet?").  Owner: FE2
 *
 * Replaces an unexplainable score with a point-by-point audit trail. Every
 * indicator shows its rule id, its weight and the concrete evidence behind it,
 * because Section 63 BSA 2023 requires explaining how the output was produced.
 */

import { ConfidenceTag, Empty, RiskPill, short } from '../components/ui'
import { riskColor } from '../api'

function Gauge({ score, level }) {
  const c = riskColor(level)
  return (
    <div className="flex items-center gap-3">
      <div className="relative w-16 h-16 shrink-0">
        <svg viewBox="0 0 40 40" className="w-16 h-16 -rotate-90">
          <circle cx="20" cy="20" r="16" fill="none" stroke="#2a2438" strokeWidth="4" />
          <circle
            cx="20" cy="20" r="16" fill="none" stroke={c} strokeWidth="4"
            strokeDasharray={`${(score / 100) * 100.5} 100.5`}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 grid place-items-center">
          <span className="font-mono text-lg font-bold" style={{ color: c }}>
            {score}
          </span>
        </div>
      </div>
      <div className="min-w-0">
        <div className="label">Algorithmic risk score</div>
        <div className="font-mono text-sm mt-0.5" style={{ color: c }}>
          {level}
        </div>
        <div className="text-[10px] text-slate-500 mt-0.5">out of 100</div>
      </div>
    </div>
  )
}

const BANDS = [
  ['CRITICAL', 75, 100],
  ['HIGH', 50, 74],
  ['MEDIUM', 25, 49],
  ['LOW', 0, 24],
]

/**
 * What the panel shows before anything is selected.
 *
 * It used to render a bare "select an entity" line, so opening the Risk
 * Inspector first showed an empty pane - which reads as unfinished rather
 * than as waiting. The case-level view is the question an officer actually
 * asks first anyway: of everything traced, what should I look at?
 *
 * Everything here comes from the graph already loaded. No extra request.
 */
function CaseOverview({ nodes, onSelect }) {
  if (!nodes?.length) {
    return <Empty>Select an entity on the map to inspect its risk decomposition.</Empty>
  }

  const ranked = [...nodes].sort((a, b) => b.risk_score - a.risk_score)
  const counts = BANDS.map(([name, lo, hi]) => ({
    name,
    n: nodes.filter((x) => x.risk_score >= lo && x.risk_score <= hi).length,
    color: riskColor(name),
  }))
  const seed = nodes.find((n) => n.is_seed)
  const actionable = ranked.filter((n) => n.risk_score >= 50).length

  return (
    <div className="p-4 space-y-4 overflow-y-auto h-full">
      <div>
        <div className="label mb-1">Case risk overview</div>
        <p className="text-[11px] text-slate-500 leading-relaxed">
          {nodes.length} entities scored against seven deterministic rules.
          {' '}
          <span className="text-slate-300">
            {actionable} at HIGH or above.
          </span>{' '}
          Select any entity to see the arithmetic behind its score.
        </p>
      </div>

      {/* Distribution. Widths are shares of the traced set, so a band with no
          entities simply does not render rather than showing a zero sliver. */}
      <div>
        <div className="flex h-2 rounded overflow-hidden bg-panel2">
          {counts.filter((c) => c.n > 0).map((c) => (
            <div
              key={c.name}
              title={`${c.n} ${c.name}`}
              style={{
                width: `${(c.n / nodes.length) * 100}%`,
                background: c.color,
              }}
            />
          ))}
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2">
          {counts.map((c) => (
            <span key={c.name} className="flex items-center gap-1.5 text-[10px]">
              <i className="w-2 h-2 rounded-full" style={{ background: c.color }} />
              <span className="text-slate-500">{c.name}</span>
              <span className="font-mono text-slate-300">{c.n}</span>
            </span>
          ))}
        </div>
      </div>

      {seed && (
        <div className="rounded border border-edge bg-panel2 px-3 py-2">
          <div className="label mb-1">Case seed</div>
          <button
            onClick={() => onSelect?.(seed.id)}
            className="font-mono text-[11px] text-slate-200 break-all text-left
                       hover:text-violet-200"
          >
            {seed.id}
          </button>
          <div className="flex items-center gap-2 mt-1.5">
            <RiskPill level={seed.risk_level} score={seed.risk_score} />
            <span className="text-[10px] text-slate-500">
              {seed.label ?? 'Unlabelled'}
            </span>
          </div>
        </div>
      )}

      <div>
        <div className="label mb-2">Ranked by score</div>
        <ul className="space-y-1">
          {ranked.slice(0, 8).map((n) => (
            <li key={n.id}>
              <button
                onClick={() => onSelect?.(n.id)}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded
                           bg-panel2 hover:bg-panel text-left border border-transparent
                           hover:border-violet/40"
              >
                <span
                  className="w-1 self-stretch rounded"
                  style={{ background: riskColor(n.risk_level) }}
                />
                <span className="font-mono text-[10px] text-slate-300 truncate flex-1">
                  {short(n.id)}
                </span>
                <span className="text-[10px] text-slate-600 truncate max-w-[92px]">
                  {n.label ?? n.type}
                </span>
                <RiskPill level={n.risk_level} score={n.risk_score} />
              </button>
            </li>
          ))}
        </ul>
      </div>

      <p className="text-[10px] text-slate-600 leading-relaxed pt-2
                    border-t border-edge">
        Scores come from seven fixed rules with cited evidence. No model
        contributes to any figure on this screen.
      </p>
    </div>
  )
}

export default function RiskInspector({ risk, node, nodes, onSelect }) {
  if (!node) return <CaseOverview nodes={nodes} onSelect={onSelect} />
  if (!risk) return <Empty>No assessment available for this entity.</Empty>

  const total = risk.indicators.reduce((s, i) => s + i.points, 0)

  return (
    <div className="p-4 space-y-4 overflow-y-auto h-full">
      <div>
        <div className="label mb-1">Inspected entity</div>
        <div className="font-mono text-xs text-slate-200 break-all">{node.id}</div>
        <div className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-2">
          {node.label ?? 'Unlabelled'}
          <ConfidenceTag value={node.label_confidence} />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-px bg-edge rounded overflow-hidden">
        {[
          ['Chain', node.chain],
          ['Balance', node.balance?.toLocaleString('en-IN') ?? '—'],
          ['Illicit', `${(node.illicit_ratio * 100).toFixed(0)}%`],
        ].map(([k, v]) => (
          <div key={k} className="bg-panel2 px-2 py-1.5">
            <div className="label text-[9px]">{k}</div>
            <div className="font-mono text-[11px] text-slate-300 truncate">{v}</div>
          </div>
        ))}
      </div>

      <Gauge score={risk.score} level={risk.level} />

      <div>
        <div className="label mb-2">Score decomposition · "why?"</div>
        {risk.indicators.length === 0 ? (
          <p className="text-[11px] text-slate-600">
            No indicators fired. This entity is in the traced set but nothing
            scored against it.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {risk.indicators.map((i) => (
              <li key={i.rule_id} className="bg-panel2 rounded px-2.5 py-2">
                <div className="flex items-start gap-2 flex-wrap">
                  <span className="font-mono text-[10px] text-violet font-bold pt-0.5">
                    {i.rule_id}
                  </span>
                  <span className="font-mono text-xs font-bold text-risk-high">
                    +{i.points}
                  </span>
                  {/* Never truncate an indicator name - this panel is what a
                      judge reads to understand why the score is what it is. */}
                  <span className="text-[11px] text-slate-300 flex-1 min-w-[110px] leading-snug">
                    {i.name}
                  </span>
                  <ConfidenceTag value={i.confidence} />
                </div>
                <div className="mt-1 font-mono text-[10px] text-slate-500 break-all leading-relaxed">
                  {i.evidence}
                </div>
              </li>
            ))}
          </ul>
        )}
        <div className="flex justify-between mt-2 pt-2 border-t border-edge
                        font-mono text-[11px]">
          <span className="text-slate-500">TOTAL</span>
          <span className="text-slate-200 font-bold">{total} / 100</span>
        </div>
      </div>

      <div className="pt-2 border-t border-edge text-[10px] text-slate-600 font-mono
                      leading-relaxed">
        engine {risk.engine_version} · deterministic · reproducible
        <br />
        computed {short(risk.computed_at, 19, 0)}
      </div>
    </div>
  )
}
