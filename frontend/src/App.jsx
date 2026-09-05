/**
 * PHASE 1 VERIFICATION SHELL.
 *
 * This is not the final UI. It exists to prove the fixture pipeline is wired
 * end to end - case, graph, risk and dilution all rendering from the frozen
 * contract with the backend switched off.
 *
 * FE1 and FE2 replace this with the real organs in Phase 3. The mockup
 * (image.png) is the visual target; this file is the working foundation.
 */

import { useEffect, useState } from 'react'
import {
  DEMO_CASE_ID,
  USE_MOCKS,
  getCase,
  getDilution,
  getGraph,
  getHealth,
  inr,
  riskColor,
} from './api'

function Banner() {
  return (
    <div className="bg-amber-500/15 border-b border-amber-500/40 px-4 py-1.5
                    text-[11px] tracking-wide text-amber-300 flex gap-3">
      <span className="font-bold">⚠ DEMONSTRATION &amp; SYNTHETIC DATA MODE</span>
      <span className="text-amber-300/60">
        Analytical leads only · not a finding of guilt · Sec 94 BNSS 2023
        verification required
      </span>
    </div>
  )
}

function Stat({ label, value, accent }) {
  return (
    <div className="px-4 py-3 border-r border-edge last:border-r-0 min-w-0">
      <div className="label">{label}</div>
      <div
        className="font-mono text-lg mt-0.5 truncate"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </div>
    </div>
  )
}

function RiskPill({ level, score }) {
  return (
    <span
      className="font-mono text-[11px] font-bold px-2 py-0.5 rounded"
      style={{ color: riskColor(level), background: `${riskColor(level)}1f` }}
    >
      {score} · {level}
    </span>
  )
}

export default function App() {
  const [state, setState] = useState({ loading: true, error: null })

  useEffect(() => {
    Promise.all([
      getHealth(),
      getCase(DEMO_CASE_ID),
      getGraph(DEMO_CASE_ID),
      getDilution(DEMO_CASE_ID),
    ])
      .then(([health, kase, graph, dilution]) =>
        setState({ loading: false, error: null, health, kase, graph, dilution })
      )
      .catch((e) => setState({ loading: false, error: e.message }))
  }, [])

  if (state.loading)
    return <div className="p-8 font-mono text-slate-500">Loading case…</div>

  if (state.error)
    return (
      <div className="p-8 font-mono text-risk-critical">
        Failed to load: {state.error}
      </div>
    )

  const { kase, graph, dilution } = state
  const nodes = graph.elements.nodes.map((n) => n.data)
  const rescue = dilution.steps.find((s) => !s.flagged)

  return (
    <div className="min-h-screen">
      <Banner />

      <header className="border-b border-edge bg-panel">
        <div className="px-5 py-3 flex items-baseline gap-3 flex-wrap">
          <span className="text-violet font-bold tracking-tight">
            PROJECT VIOLET MILK
          </span>
          <span className="text-slate-600">/</span>
          <span className="text-sm text-slate-400">
            Chandigarh Police Cyber Crime Unit
          </span>
          <span className="ml-auto font-mono text-[11px] text-slate-500">
            {USE_MOCKS ? '◉ FIXTURES' : '◉ LIVE BACKEND'} · {graph.stats.source}
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 border-t border-edge">
          <Stat label="Case" value={kase.case_id} />
          <Stat label="NCRP Ref" value={kase.ncrp_ref} />
          <Stat label="Victim loss" value={inr(kase.victim_amount_inr)} accent="#e5901d" />
          <Stat label="Nodes / Edges" value={`${graph.stats.nodes} / ${graph.stats.edges}`} />
          <Stat label="Max depth" value={graph.stats.max_depth_reached} />
        </div>
      </header>

      <main className="p-5 grid gap-5 lg:grid-cols-3">
        {/* ---------------------------------------------------- entities */}
        <section className="organ lg:col-span-2 overflow-hidden">
          <div className="px-4 py-2.5 border-b border-edge label">
            Traced entities · {nodes.length}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left">
                  {['Entity', 'Type', 'Illicit %', 'Risk'].map((h) => (
                    <th key={h} className="label px-4 py-2 border-b border-edge">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {nodes.map((n) => (
                  <tr key={n.id} className="border-b border-edge/50">
                    <td className="px-4 py-2">
                      <div className="font-mono text-xs text-slate-300 truncate max-w-[220px]">
                        {n.id}
                      </div>
                      <div className="text-[11px] text-slate-500">
                        {n.label}
                        {n.is_seed && (
                          <span className="ml-1.5 text-violet font-bold">SEED</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-400">{n.type}</td>
                    <td className="px-4 py-2 font-mono text-xs tabular-nums">
                      {(n.illicit_ratio * 100).toFixed(0)}%
                    </td>
                    <td className="px-4 py-2">
                      <RiskPill level={n.risk_level} score={n.risk_score} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* ---------------------------------------------------- dilution */}
        <section className="organ h-fit">
          <div className="px-4 py-2.5 border-b border-edge label">
            Dilution · haircut model
          </div>
          <div className="p-4 space-y-3">
            {dilution.steps.map((s) => (
              <div key={s.node_id} className="text-xs">
                <div className="font-mono text-slate-400 truncate">{s.node_id}</div>
                <div className="flex items-center gap-2 mt-1">
                  <div className="flex-1 h-1.5 bg-edge rounded overflow-hidden">
                    <div
                      className="h-full"
                      style={{
                        width: `${s.illicit_ratio * 100}%`,
                        background: s.flagged ? '#e5484d' : '#3d9a6d',
                      }}
                    />
                  </div>
                  <span className="font-mono tabular-nums w-10 text-right">
                    {(s.illicit_ratio * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ))}

            {rescue && (
              <div className="mt-4 pt-3 border-t border-edge text-[11px] leading-relaxed text-slate-400">
                <span className="text-risk-low font-bold">NOT FLAGGED · </span>
                the clean pool falls to{' '}
                <span className="font-mono text-slate-200">
                  {(rescue.illicit_ratio * 100).toFixed(0)}%
                </span>
                , below the {dilution.threshold * 100}% reporting threshold.
                Proportional haircut prevents a false positive on legitimate
                liquidity.
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  )
}
