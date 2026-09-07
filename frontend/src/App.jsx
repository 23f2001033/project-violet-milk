/**
 * Application shell — "The Violet Milk Map".
 *
 * Layout follows the approved mockup: a persistent demonstration banner, an
 * organ rail on the left, the working surface in the centre, and the evidence
 * inspector on the right when a graph entity is selected.
 *
 * Selection is held here so the graph, timeline, risk inspector and dilution
 * panel all stay synchronised on the same entity.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  DEMO_CASE_ID,
  USE_MOCKS,
  getAudit,
  getCase,
  getDilution,
  getAnomaly,
  getAssets,
  getGraph,
  getRisk,
  getTimeline,
  inr,
  getToken,
  listEvidence,
  logout,
  verifyAudit,
  whoami,
} from './api'
import { Button, ErrorBox, RiskPill, Spinner, short } from './components/ui'
import Login from './components/Login'
import CommandCenter from './organs/CommandCenter'
import CaseIntake from './organs/CaseIntake'
import EvidenceUploader from './organs/EvidenceUploader'
import GraphVisualiser from './organs/GraphVisualiser'
import Timeline from './organs/Timeline'
import RiskInspector from './organs/RiskInspector'
import DilutionPanel from './organs/DilutionPanel'
import FlagAgent from './organs/FlagAgent'
import ReportExport from './organs/ReportExport'
import AuditLog from './organs/AuditLog'
import AssetLedger from './organs/AssetLedger'

const ORGANS = [
  { id: 'command', label: 'Command Center', icon: '▣' },
  { id: 'intake', label: 'Case Intake', icon: '▤' },
  { id: 'evidence', label: 'Evidence Ingestion', icon: '▥' },
  { id: 'graph', label: 'Graph Visualiser', icon: '◈' },
  { id: 'assets', label: 'Asset Ledger', icon: '₹' },
  { id: 'timeline', label: 'Timeline', icon: '◷' },
  { id: 'risk', label: 'Risk Inspector', icon: '◉' },
  { id: 'dilution', label: 'Dilution Calculator', icon: '◐' },
  { id: 'flag', label: 'Flag Agent (ML)', icon: '⚑' },
  { id: 'dossier', label: 'Sec 63 BSA Dossier', icon: '▦' },
  { id: 'audit', label: 'Chain of Custody', icon: '⛓' },
]

function Banner() {
  return (
    <div className="shrink-0 bg-amber-500/15 border-b border-amber-500/40 px-4 py-1
                    text-[10px] tracking-wide text-amber-300 flex gap-3 items-center
                    flex-wrap">
      <span className="font-bold">⚠ DEMONSTRATION &amp; SYNTHETIC DATA MODE ACTIVE</span>
      <span className="text-amber-300/60 hidden md:inline">
        Hackathon prototype · synthetic case data · not an official police system
      </span>
      <span className="ml-auto font-mono text-amber-300/70">
        {USE_MOCKS ? 'FIXTURES' : 'LIVE BACKEND'}
      </span>
    </div>
  )
}

export default function App() {
  const [organ, setOrgan] = useState('command')
  const [selected, setSelected] = useState(null)
  // Live mainnet is held entirely in local state and never written back to the
  // case. The scripted demo path stays intact no matter what gets traced live.
  const [live, setLive] = useState({ on: false, addr: '', busy: false,
                                     graph: null, error: null })
  const [inspectorTab, setInspectorTab] = useState('risk')
  const [data, setData] = useState({ loading: true })
  // null = not signed in, undefined = still checking a stored token
  const [session, setSession] = useState(getToken() ? undefined : null)

  // A stored token may have expired while the tab was closed. Confirm it
  // before rendering the workspace, so we never show a shell that then fails
  // every request.
  useEffect(() => {
    if (session !== undefined) return
    whoami()
      .then((user) => setSession({ user }))
      .catch(() => setSession(null))
  }, [session])

  const load = useCallback(() => {
    if (!session) return
    setData({ loading: true })
    Promise.all([
      getCase(DEMO_CASE_ID),
      getGraph(DEMO_CASE_ID),
      getDilution(DEMO_CASE_ID),
      getTimeline(DEMO_CASE_ID),
      getAudit(DEMO_CASE_ID),
      listEvidence(DEMO_CASE_ID),
      // The Flag Agent must never block the case view: a model failure is a
      // missing panel, not a broken dashboard.
      getAnomaly(DEMO_CASE_ID).catch(() => null),
      verifyAudit(DEMO_CASE_ID).catch(() => null),
      // Same rule as the Flag Agent: the asset ledger is a derived view, so a
      // failure here is a missing panel, never a broken case.
      getAssets(DEMO_CASE_ID).catch(() => null),
    ])
      .then(
        ([kase, graph, dilution, timeline, audit, evidence, anomaly,
          verification, assets]) =>
          setData({
            loading: false, kase, graph, dilution, timeline, audit, evidence,
            anomaly, verification, assets,
          })
      )
      .catch((e) => {
        if (e.message === 'SESSION_EXPIRED') {
          setSession(null)
          return
        }
        setData({ loading: false, error: e.message })
      })
  }, [session])

  useEffect(load, [load])

  const nodesById = useMemo(() => {
    if (!data.graph) return {}
    return Object.fromEntries(
      data.graph.elements.nodes.map((n) => [n.data.id, n.data])
    )
  }, [data.graph])

  // Risk assessments come from the graph payload for every node; the seed's
  // full indicator breakdown is the one the fixture carries in detail.
  const [riskCache, setRiskCache] = useState({})
  useEffect(() => {
    if (!selected || riskCache[selected]) return
    getRisk(DEMO_CASE_ID, selected)
      .then((r) => setRiskCache((c) => ({ ...c, [selected]: r })))
      .catch(() => {})
  }, [selected, riskCache])

  if (session === undefined) return <Spinner label="Restoring session…" />
  if (session === null) {
    return <Login onSignedIn={(s) => setSession(s)} />
  }
  if (data.loading) return <Spinner label="Loading case…" />
  if (data.error) return <ErrorBox error={data.error} onRetry={load} />

  const { kase, dilution, timeline, audit } = data
  // The live trace, when one is loaded, replaces the displayed graph only.
  const graph = live.on && live.graph ? live.graph : data.graph
  const evidence = data.evidence ?? []
  const verified = evidence.filter((e) => e.hash_match).length
  async function runLiveTrace() {
    // Tron was supported by the backend and rejected here, so pasting the very
    // rail Indian proceeds move on failed with "enter a valid 0x address".
    // Base58 is case-SENSITIVE, so only the hex form may be lowercased.
    const raw = live.addr.trim()
    const isEth = /^0x[0-9a-fA-F]{40}$/.test(raw)
    const isTron = /^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(raw)
    if (!isEth && !isTron) {
      setLive((s) => ({
        ...s,
        error: 'Enter an Ethereum address (0x…, 42 chars) or a Tron address (T…, 34 chars).',
      }))
      return
    }
    const addr = isEth ? raw.toLowerCase() : raw
    setLive((s) => ({ ...s, busy: true, error: null }))
    try {
      const g = await getGraph(kase.case_id, addr, 'live')
      setLive((s) => ({ ...s, busy: false, graph: g, on: true }))
      // Deliberately NOT auto-selecting the seed. Selecting a node pans the
      // canvas to centre it, which fought the initial fit and left the fresh
      // trace pinned to one edge. After a trace the right thing to show is the
      // whole neighbourhood; the operator clicks in from there.
      setSelected(null)
      setOrgan('graph')
    } catch (e) {
      setLive((s) => ({ ...s, busy: false, error: e.message }))
    }
  }

  const selectNode = (id) => {
    setSelected(id)
    if (id && !['graph', 'timeline'].includes(organ)) setOrgan('graph')
  }

  const showInspector = ['graph', 'risk', 'dilution'].includes(organ)

  const main = {
    command: (
      <CommandCenter
        kase={kase} graph={graph} dilution={dilution} audit={audit}
        onOpen={selectNode}
      />
    ),
    intake: <CaseIntake kase={kase} onSaved={load} />,
    evidence: (
      <EvidenceUploader
        caseId={kase.case_id} evidence={evidence} onUploaded={load}
      />
    ),

    graph: (
      <div className="grid grid-rows-[1fr_auto] h-full min-h-0">
        <GraphVisualiser
          graph={graph} selected={selected} onSelect={setSelected}
          assets={data.assets} risk={riskCache[selected]}
        />
        <div className="border-t border-edge max-h-[210px] overflow-hidden">
          <div className="label px-4 py-2 border-b border-edge">
            Synchronised chronology · {timeline.length} events
          </div>
          <div className="max-h-[160px] overflow-y-auto">
            <Timeline timeline={timeline} selected={selected} onSelect={setSelected} />
          </div>
        </div>
      </div>
    ),
    assets: (
      <AssetLedger
        assets={data.assets} selected={selected} nodesById={nodesById}
      />
    ),
    timeline: <Timeline timeline={timeline} selected={selected} onSelect={setSelected} />,
    risk: (
      <RiskInspector
        risk={riskCache[selected]} node={selected ? nodesById[selected] : null}
        nodes={graph.elements.nodes.map((n) => n.data)} onSelect={setSelected}
      />
    ),
    dilution: (
      <DilutionPanel dilution={dilution} selected={selected} onSelect={setSelected} />
    ),
    flag: (
      <FlagAgent
        anomaly={data.anomaly}
        nodes={graph.elements.nodes.map((n) => n.data)}
        selected={selected}
        onSelect={selectNode}
      />
    ),
    dossier: <ReportExport kase={kase} />,
    audit: <AuditLog audit={audit} verification={data.verification} />,
  }[organ]

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Banner />
      {session.warning && (
        <div className="shrink-0 bg-risk-critical/15 border-b
                        border-risk-critical/40 px-4 py-1 text-[10px]
                        text-risk-critical">
          <span className="font-bold">⚠ DEFAULT PASSWORD IN USE</span>
          <span className="ml-2 text-risk-critical/80">{session.warning}</span>
        </div>
      )}

      <header className="shrink-0 border-b border-edge bg-panel">
        <div className="px-4 py-2.5 flex items-center gap-3 flex-wrap">
          <div className="min-w-0">
            <div className="text-[10px] tracking-[0.15em] text-slate-500">
              CHANDIGARH POLICE HACKATHON
            </div>
            <div className="text-violet font-bold tracking-tight leading-tight">
              PROJECT VIOLET MILK
            </div>
          </div>
          {/* Reflects the actual data source, not a certification claim. */}
          <span
            className="font-mono text-[9px] px-1.5 py-0.5 rounded border"
            style={
              graph.stats.source === 'SyntheticSource'
                ? { color: '#e5901d', background: '#e5901d1a', borderColor: '#e5901d66' }
                : { color: '#e5484d', background: '#e5484d1a', borderColor: '#e5484d66' }
            }
          >
            {graph.stats.source === 'SyntheticSource' ? 'SYNTHETIC' : 'LIVE MAINNET'}
          </span>
          <div className="ml-auto flex items-center gap-3">
            <div className="text-right leading-tight hidden sm:block">
              <div className="text-[11px] text-slate-300">
                {session.user?.display_name ?? session.user?.user_id}
              </div>
              <div className="text-[9px] text-slate-600">
                {session.user?.rank || session.user?.user_id}
              </div>
            </div>
            <Button variant="primary" onClick={() => setOrgan('dossier')}>
              Export Court Dossier
            </Button>
            <Button
              onClick={() => {
                logout()
                setSession(null)
              }}
            >
              Sign out
            </Button>
          </div>
        </div>

        {/* ------------------------------------------- live mainnet bar */}
        <div className="flex flex-wrap items-center gap-2 px-4 py-1.5
                        border-t border-edge">
          <div className="flex rounded overflow-hidden border border-edge">
            <button
              onClick={() => setLive((s) => ({ ...s, on: false }))}
              className={`px-2.5 py-1 text-[10px] font-mono tracking-wider
                ${!live.on ? 'bg-violet/25 text-slate-100'
                           : 'text-slate-500 hover:text-slate-300'}`}
            >
              ◉ DEMO
            </button>
            <button
              onClick={() => setLive((s) => ({ ...s, on: true }))}
              className={`px-2.5 py-1 text-[10px] font-mono tracking-wider
                ${live.on ? 'bg-risk-critical/25 text-risk-critical'
                          : 'text-slate-500 hover:text-slate-300'}`}
            >
              ◉ LIVE MAINNET
            </button>
          </div>

          {live.on && (
            <>
              <input
                value={live.addr}
                onChange={(e) => setLive((s) => ({ ...s, addr: e.target.value }))}
                onKeyDown={(e) => e.key === 'Enter' && runLiveTrace()}
                placeholder="0x… (Ethereum) or T… (Tron / USDT-TRC20)"
                spellCheck={false}
                className="flex-1 min-w-[260px] bg-panel2 border border-edge rounded
                           px-2 py-1 text-[11px] font-mono text-slate-200
                           placeholder:text-slate-700 focus:border-violet
                           focus:outline-none"
              />
              <Button onClick={runLiveTrace} disabled={live.busy}>
                {live.busy ? 'Tracing mainnet…' : 'Trace'}
              </Button>
              {live.error && (
                <span className="text-[10px] text-risk-critical font-mono">
                  {live.error}
                </span>
              )}
              {live.graph && !live.error && (
                <span className="text-[10px] text-slate-500 font-mono">
                  {live.graph.stats.nodes} entities · {live.graph.stats.edges}{' '}
                  transfers
                  {live.graph.stats.truncated && ' · bounds reached'}
                </span>
              )}
            </>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-1.5
                        border-t border-edge text-[11px] font-mono text-slate-500">
          <span className="text-slate-300">{kase.case_id}</span>
          <span>NCRP {kase.ncrp_ref}</span>
          <span className="text-risk-high">{inr(kase.victim_amount_inr)}</span>
          <span>{graph.stats.nodes} entities · {graph.stats.edges} transfers</span>
          {graph.stats.ingested_edges > 0 && (
            <span className="text-risk-high">
              +{graph.stats.ingested_edges} ingested
            </span>
          )}
          <span>depth {graph.stats.max_depth_reached}</span>
          <span className="ml-auto">{graph.stats.source}</span>
        </div>
      </header>

      {/* Narrow-viewport navigation. The left rail below is lg-and-up only, so
          without this strip a smaller projector or window would leave the
          operator with no way to switch organs at all. */}
      <nav className="lg:hidden shrink-0 flex overflow-x-auto border-b border-edge
                      bg-panel">
        {ORGANS.map((o) => (
          <button
            key={o.id}
            onClick={() => setOrgan(o.id)}
            className={`shrink-0 px-3 py-2 text-[11px] whitespace-nowrap border-b-2
              transition-colors ${
                organ === o.id
                  ? 'border-violet text-slate-100 bg-violet/10'
                  : 'border-transparent text-slate-500 hover:text-slate-200'
              }`}
          >
            <span className="text-violet/70 mr-1.5">{o.icon}</span>
            {o.label}
          </button>
        ))}
      </nav>

      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[190px_1fr]
                      xl:grid-cols-[190px_1fr_320px]">
        {/* -------------------------------------------------- organ rail */}
        <nav className="hidden lg:flex flex-col border-r border-edge bg-panel
                        overflow-y-auto">
          <div className="label px-3 py-2.5 border-b border-edge">
            Investigation organs
          </div>
          {ORGANS.map((o) => (
            <button
              key={o.id}
              onClick={() => setOrgan(o.id)}
              className={`flex items-center gap-2.5 px-3 py-2 text-[11px] text-left
                border-l-2 transition-colors ${
                  organ === o.id
                    ? 'border-violet bg-violet/10 text-slate-100'
                    : 'border-transparent text-slate-500 hover:text-slate-200 hover:bg-panel2'
                }`}
            >
              <span className="text-violet/70 w-3">{o.icon}</span>
              {o.label}
            </button>
          ))}
          {/* Derived from the real evidence register: a file is "verified"
              only when the browser hash and the server hash actually agree.
              This previously read "SHA-256 chain valid" unconditionally - a
              false integrity claim in a forensics tool. */}
          <div className="mt-auto p-3 border-t border-edge">
            <div className="label mb-1">Evidence integrity</div>
            {evidence.length === 0 ? (
              <div className="font-mono text-[10px] text-slate-600">
                no files ingested
              </div>
            ) : verified === evidence.length ? (
              <div className="font-mono text-[10px] text-risk-low">
                ✓ {verified}/{evidence.length} hash-verified
              </div>
            ) : (
              <div className="font-mono text-[10px] text-risk-critical">
                ✗ {evidence.length - verified} of {evidence.length} failed
              </div>
            )}
          </div>
        </nav>

        {/* ------------------------------------------------ working surface */}
        <main className="min-w-0 min-h-0 overflow-hidden bg-ground">{main}</main>

        {/* --------------------------------------------------- inspector */}
        {showInspector && (
          <aside className="hidden xl:flex flex-col border-l border-edge bg-panel
                            min-h-0">
            <div className="flex border-b border-edge shrink-0">
              {[
                ['risk', 'Risk "why?"'],
                ['dilution', 'Dilution decay'],
              ].map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setInspectorTab(id)}
                  className={`flex-1 px-3 py-2 text-[10px] uppercase tracking-wider
                    border-b-2 transition-colors ${
                      inspectorTab === id
                        ? 'border-violet text-slate-100'
                        : 'border-transparent text-slate-600 hover:text-slate-300'
                    }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="flex-1 min-h-0">
              {inspectorTab === 'risk' ? (
                <RiskInspector
                  risk={riskCache[selected]}
                  node={selected ? nodesById[selected] : null}
                />
              ) : (
                <DilutionPanel
                  dilution={dilution} selected={selected} onSelect={setSelected}
                />
              )}
            </div>
          </aside>
        )}
      </div>
    </div>
  )
}
