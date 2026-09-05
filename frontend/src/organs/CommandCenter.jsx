/**
 * ORGAN 0 — Command Center.  Owner: FE1
 * The opening screen: a worked case on display, not an empty shell.
 */

import { RiskPill, delta, timeIST } from '../components/ui'
import { inr, riskColor } from '../api'

function Metric({ label, value, sub, accent }) {
  return (
    <div className="bg-panel border border-edge rounded px-4 py-3">
      <div className="label">{label}</div>
      <div
        className="font-mono text-xl mt-1 truncate"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </div>
      {sub && <div className="text-[10px] text-slate-600 mt-0.5">{sub}</div>}
    </div>
  )
}

export default function CommandCenter({ kase, graph, dilution, audit, onOpen }) {
  const nodes = graph.elements.nodes.map((n) => n.data)
  const critical = nodes.filter(
    (n) => n.risk_level === 'CRITICAL' || n.risk_level === 'HIGH'
  )
  const flagged = dilution.steps.filter((s) => s.flagged).length
  const top = [...nodes].sort((a, b) => b.risk_score - a.risk_score).slice(0, 5)

  return (
    <div className="p-5 space-y-5 overflow-y-auto h-full">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Active case" value={kase.case_id} sub={kase.ncrp_ref} />
        <Metric
          label="Traced loss"
          value={inr(kase.victim_amount_inr)}
          sub="reported by complainant"
          accent="#e5901d"
        />
        <Metric
          label="Entities mapped"
          value={`${graph.stats.nodes} / ${graph.stats.edges}`}
          sub={`depth ${graph.stats.max_depth_reached} · ${graph.stats.source}`}
        />
        <Metric
          label="High + critical"
          value={critical.length}
          sub={`${flagged} of ${dilution.steps.length} transfers above threshold`}
          accent="#e5484d"
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="organ">
          <header className="px-4 py-2.5 border-b border-edge">
            <h2 className="label">Highest-risk entities</h2>
          </header>
          <ul>
            {top.map((n) => (
              <li
                key={n.id}
                onClick={() => onOpen?.(n.id)}
                className="flex items-center gap-3 px-4 py-2.5 border-b border-edge/50
                           last:border-0 cursor-pointer hover:bg-panel2"
              >
                <i
                  className="w-1.5 h-8 rounded-sm shrink-0"
                  style={{ background: riskColor(n.risk_level) }}
                />
                <div className="min-w-0 flex-1">
                  <div className="font-mono text-[11px] text-slate-300 truncate">
                    {n.id}
                  </div>
                  <div className="text-[10px] text-slate-600 truncate">
                    {n.label} · {(n.illicit_ratio * 100).toFixed(0)}% traced funds
                  </div>
                </div>
                <RiskPill level={n.risk_level} score={n.risk_score} />
              </li>
            ))}
          </ul>
        </section>

        <section className="organ">
          <header className="px-4 py-2.5 border-b border-edge">
            <h2 className="label">Chain of custody · recent</h2>
          </header>
          <ul>
            {audit.slice(-6).reverse().map((a) => (
              <li
                key={a.audit_id}
                className="px-4 py-2 border-b border-edge/50 last:border-0"
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] text-slate-600">
                    {timeIST(a.timestamp)}
                  </span>
                  <span className="font-mono text-[10px] text-violet">
                    {a.action}
                  </span>
                  <span className="text-[10px] text-slate-600 ml-auto">
                    {a.user_id}
                  </span>
                </div>
                <div className="font-mono text-[10px] text-slate-500 truncate mt-0.5">
                  {a.target}
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <p className="text-[10px] text-slate-600 leading-relaxed max-w-3xl">
        This workspace produces <strong className="text-slate-500">investigative
        leads and supporting paperwork</strong>. It does not identify account
        holders. Naming an owner requires a Section 94 BNSS 2023 production
        order to the exchange for KYC records — the dossier generated here is
        the annexure that justifies that order.
      </p>
    </div>
  )
}
