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
  listCases,
  runTrace,
  USE_MOCKS,
  getAudit,
  getCase,
  getDilution,
  getAnomaly,
  getAssets,
  getConversions,
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
    <div className="banner-warn shrink-0 border-b px-4 py-1
                    text-[10px] tracking-wide flex gap-3 items-center
                    flex-wrap">
      <span className="font-bold">⚠ DEMONSTRATION &amp; SYNTHETIC DATA MODE ACTIVE</span>
      <span className="banner-sub hidden md:inline">
        Hackathon prototype · synthetic case data · not an official police system
      </span>
      <span className="banner-tag ml-auto font-mono">
        {USE_MOCKS ? 'FIXTURES' : 'LIVE BACKEND'}
      </span>
    </div>
  )
}

const THEME_KEY = 'vm.theme'

function useTheme() {
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem(THEME_KEY) || 'dark' } catch { return 'dark' }
  })
  useEffect(() => {
    // Dark is the default, so it is the ABSENCE of the stamp - that keeps
    // :root the dark palette and the light theme a single override block.
    const root = document.documentElement
    if (theme === 'light') root.setAttribute('data-theme', 'light')
    else root.removeAttribute('data-theme')
    try { localStorage.setItem(THEME_KEY, theme) } catch { /* private mode */ }
  }, [theme])
  return [theme, () => setTheme((t) => (t === 'light' ? 'dark' : 'light'))]
}


/**
 * The case as an officer receives it, before any analysis exists.
 *
 * Everything on this screen is a fact from the FIR - it is not output. That is
 * the point: when the dashboard fills a moment later, a judge can tell which
 * figures the software computed, because they were not here before.
 */
function Briefing({ kase, evidence, running, error, onRun, user }) {
  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-3xl mx-auto">
        <div className="label mb-2">Case assigned</div>
        <h1 className="text-[22px] font-bold text-slate-100 tracking-tight">
          {kase.case_id}
        </h1>
        <p className="text-[12px] text-slate-500 mt-1">
          Received by {user?.display_name ?? user?.user_id} ·{' '}
          {user?.rank ?? 'unassigned'}
        </p>

        <div className="organ mt-5 divide-y divide-edge">
          {[
            ['FIR reference', kase.fir_ref],
            ['NCRP acknowledgement', kase.ncrp_ref],
            ['Complainant', kase.victim_name],
            ['Reported loss', inr(kase.victim_amount_inr)],
            ['Incident recorded', (kase.incident_datetime || '').replace('T', ' ')],
            ['Address to trace', kase.seed_wallet],
            ['Bank reference (UTR)', kase.seed_utr || 'not supplied'],
          ].map(([k, v]) => (
            <div key={k} className="flex flex-wrap gap-x-4 gap-y-1 px-4 py-2.5">
              <div className="label w-[168px] shrink-0 pt-0.5">{k}</div>
              <div className="font-mono text-[12px] text-slate-200 break-all flex-1">
                {v || '—'}
              </div>
            </div>
          ))}
        </div>

        {kase.notes && (
          <p className="text-[12px] text-slate-400 leading-relaxed mt-3
                        max-w-2xl">
            {kase.notes}
          </p>
        )}

        <div className="mt-5 flex items-center gap-3 flex-wrap">
          <button
            onClick={onRun}
            disabled={running}
            className="px-5 py-2.5 rounded bg-violet text-white text-[13px]
                       font-semibold hover:brightness-110 disabled:opacity-60
                       disabled:cursor-not-allowed"
          >
            {running ? 'Tracing…' : 'Begin investigation'}
          </button>
          <span className="text-[11px] text-slate-500">
            {running
              ? 'Following the money from the address above.'
              : `Traces the address above, scores every entity it reaches against
                 seven rules, and records the run in the chain of custody.`}
          </span>
        </div>

        {error && (
          <div className="mt-3 text-[11px] text-risk-critical font-mono">
            {error}
          </div>
        )}

        <div className="mt-6 pt-4 border-t border-edge">
          <div className="label mb-1.5">
            Evidence on file · {evidence?.length ?? 0}
          </div>
          {evidence?.length ? (
            <ul className="space-y-1">
              {evidence.map((e) => (
                <li key={e.evidence_id}
                    className="font-mono text-[11px] text-slate-400">
                  {e.filename}
                  <span className="text-slate-600">
                    {' '}· {e.row_count ?? '—'} rows ·{' '}
                    {e.hash_match ? 'hash verified' : 'HASH MISMATCH'}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[11px] text-slate-600">
              No files ingested. The trace will run on the case record alone.
            </p>
          )}
        </div>

        <p className="text-[10px] text-slate-600 leading-relaxed mt-6 max-w-2xl">
          Nothing above is produced by this software. It is the case as it
          arrives &mdash; the complaint, the amount, and one address. Every
          figure that appears after the trace is computed from those inputs by
          seven documented rules.
        </p>
      </div>
    </div>
  )
}

export default function App() {
  const [theme, toggleTheme] = useTheme()
  const [organ, setOrgan] = useState('command')
  const [selected, setSelected] = useState(null)
  // Live mainnet is held entirely in local state and never written back to the
  // case. The scripted demo path stays intact no matter what gets traced live.
  const [live, setLive] = useState({ on: false, addr: '', busy: false,
                                     graph: null, error: null })
  const [inspectorTab, setInspectorTab] = useState('risk')
  // The organ rail collapses to an icon strip. On a projector the graph is the
  // thing the room is looking at, and 190px of navigation it has already read
  // is 190px the canvas does not get. The choice is remembered so a rehearsed
  // demo opens the way it was left.
  const [railOpen, setRailOpen] = useState(() => {
    try { return localStorage.getItem('vm.rail') !== 'closed' } catch { return true }
  })
  useEffect(() => {
    try { localStorage.setItem('vm.rail', railOpen ? 'open' : 'closed') } catch {}
  }, [railOpen])
  // The chronology strip under the graph, likewise. It is useful while reading
  // the trace and in the way while presenting it.
  const [chronOpen, setChronOpen] = useState(true)
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

  // Each officer opens their own case. The case list is fetched first so the
  // one owned by the signed-in user can be resolved; the bundled demo case is
  // the fallback, which is also what an unrecognised account gets.
  // TWO PHASES, on purpose.
  //
  // The dashboard used to arrive fully populated, which reads as a mockup: a
  // judge cannot tell computed figures from typed ones. Now the case BRIEFING
  // loads on sign-in - the FIR, the complainant, the amount, the seed address,
  // the facts an officer already has - and the analysis only exists after
  // someone runs it.
  //
  // The button is not a loading animation. It POSTs the trace, which is an
  // audited action: a TRACE_RUN entry is written to the hash-chained custody
  // log against the signed-in officer before any panel appears.
  const brief = useCallback(async () => {
    if (!session) return
    setData({ loading: true })
    let caseId = DEMO_CASE_ID
    try {
      const mine = (await listCases()).find(
        (c) => c.io_name === session.user?.user_id
      )
      if (mine) caseId = mine.case_id
      const [kase, evidence] = await Promise.all([
        getCase(caseId), listEvidence(caseId).catch(() => []),
      ])
      setData({ loading: false, caseId, kase, evidence, started: false })
    } catch (e) {
      if (e.message === 'SESSION_EXPIRED') return setSession(null)
      setData({ loading: false, error: e.message })
    }
  }, [session])

  const investigate = useCallback(async () => {
    const caseId = data.caseId
    const kase = data.kase
    if (!caseId || !kase) return
    setData((d) => ({ ...d, running: true, error: null }))
    try {
      // The real thing, and the reason this button is worth pressing.
      await runTrace(caseId, { seed: kase.seed_wallet, max_depth: 3 })

      const [graph, dilution, timeline, audit, evidence, anomaly,
             verification, assets, conversions] = await Promise.all([
        getGraph(caseId),
        getDilution(caseId),
        getTimeline(caseId),
        getAudit(caseId),
        listEvidence(caseId).catch(() => []),
        // A model failure is a missing panel, not a broken case.
        getAnomaly(caseId).catch(() => null),
        verifyAudit(caseId).catch(() => null),
        getAssets(caseId).catch(() => null),
        getConversions(caseId).catch(() => null),
      ])
      setData((d) => ({
        ...d, running: false, started: true, graph, dilution, timeline,
        audit, evidence, anomaly, verification, assets, conversions,
      }))
      setOrgan('command')
    } catch (e) {
      if (e.message === 'SESSION_EXPIRED') return setSession(null)
      setData((d) => ({ ...d, running: false, error: e.message }))
    }
  }, [data.caseId, data.kase])

  // `load` is what the organs call after they change something - re-running
  // the investigation is the honest way to refresh, since that is what an
  // officer would actually do.
  const load = data.started ? investigate : brief

  useEffect(() => { brief() }, [brief])
  // Switching account switches case: drop the previous graph's risk cache.
  useEffect(() => { setRiskCache({}); setSelected(null) }, [data.caseId])

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
    if (!selected || riskCache[selected] || !data.caseId) return
    getRisk(data.caseId, selected)
      .then((r) => setRiskCache((c) => ({ ...c, [selected]: r })))
      .catch(() => {})
  }, [selected, riskCache, data.caseId])

  if (session === undefined) return <Spinner label="Restoring session…" />
  if (session === null) {
    return <Login onSignedIn={(s) => setSession(s)} />
  }
  if (data.loading) return <Spinner label="Opening case…" />
  if (data.error && !data.kase) {
    return <ErrorBox error={data.error} onRetry={brief} />
  }

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

  const showInspector =
    data.started && ['graph', 'risk', 'dilution'].includes(organ)

  const main = !data.started ? null : {
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
          key={theme}
          graph={graph} selected={selected} onSelect={setSelected}
          assets={data.assets} risk={riskCache[selected]}
        />
        <div className="border-t border-edge max-h-[210px] overflow-hidden">
          <button
            onClick={() => setChronOpen((v) => !v)}
            aria-expanded={chronOpen}
            className="w-full label px-4 py-2 border-b border-edge flex items-center
                       gap-2 hover:text-slate-200 transition-colors"
          >
            <span className="font-mono text-[10px] leading-none">
              {chronOpen ? '▾' : '▸'}
            </span>
            Synchronised chronology · {timeline.length} events
            <span className="ml-auto normal-case tracking-normal text-slate-600">
              {chronOpen ? 'hide' : 'show'}
            </span>
          </button>
          {chronOpen && (
            <div className="max-h-[160px] overflow-y-auto">
              <Timeline timeline={timeline} selected={selected} onSelect={setSelected} />
            </div>
          )}
        </div>
      </div>
    ),
    assets: (
      <AssetLedger
        assets={data.assets} conversions={data.conversions}
        selected={selected} nodesById={nodesById}
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
              !graph || graph.stats.source === 'SyntheticSource'
                ? { color: '#e5901d', background: '#e5901d1a', borderColor: '#e5901d66' }
                : { color: '#e5484d', background: '#e5484d1a', borderColor: '#e5484d66' }
            }
          >
            {!graph || graph.stats.source === 'SyntheticSource'
              ? 'SYNTHETIC' : 'LIVE MAINNET'}
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
            {/* The most prominent button on the screen, and before a trace it
                also went nowhere. There is nothing to certify until the trace
                has run, so it says that instead of appearing to fail. */}
            <Button
              variant="primary"
              onClick={() => setOrgan('dossier')}
              disabled={!data.started}
              title={data.started
                ? 'Open the Sec 63 BSA dossier'
                : 'Begin the investigation first — the dossier is built from the trace'}
            >
              Export Court Dossier
            </Button>
            <button
              onClick={toggleTheme}
              title={theme === 'light' ? 'Switch to dark' : 'Switch to light'}
              aria-label={theme === 'light' ? 'Switch to dark' : 'Switch to light'}
              className="px-2.5 py-1.5 rounded border border-edge text-slate-400
                         hover:text-slate-100 hover:border-violet/50 text-[13px]
                         leading-none"
            >
              {theme === 'light' ? '☾' : '☀'}
            </button>
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
            {/* Also gated. A live trace run before the workspace exists used
                to succeed, call setOrgan('graph'), and then land nowhere,
                because the working surface is not mounted until the case
                trace has run - so a mainnet trace that actually worked looked
                like it had failed. */}
            <button
              onClick={() => setLive((s) => ({ ...s, on: true }))}
              disabled={!data.started}
              title={data.started
                ? 'Trace an address on mainnet'
                : 'Begin the investigation first, then switch to mainnet'}
              className={`px-2.5 py-1 text-[10px] font-mono tracking-wider
                ${!data.started ? 'text-slate-700 cursor-not-allowed'
                  : live.on ? 'bg-risk-critical/25 text-risk-critical'
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
          {graph ? (
            <span>
              {graph.stats.nodes} entities · {graph.stats.edges} transfers
            </span>
          ) : (
            <span className="text-slate-600">not yet traced</span>
          )}
          {graph && graph.stats.ingested_edges > 0 && (
            <span className="text-risk-high">
              +{graph.stats.ingested_edges} ingested
            </span>
          )}
          {graph && <span>depth {graph.stats.max_depth_reached}</span>}
          <span className="ml-auto">{graph?.stats.source ?? ""}</span>
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
            disabled={!data.started}
            className={`shrink-0 px-3 py-2 text-[11px] whitespace-nowrap border-b-2
              transition-colors ${
                !data.started
                  ? 'border-transparent text-slate-700 cursor-not-allowed'
                  : organ === o.id
                    ? 'border-violet text-slate-100 bg-violet/10'
                    : 'border-transparent text-slate-500 hover:text-slate-200'
              }`}
          >
            <span className="text-violet/70 mr-1.5">{o.icon}</span>
            {o.label}
          </button>
        ))}
      </nav>

      <div
        className={`flex-1 min-h-0 grid grid-cols-1 ${
          railOpen
            ? 'lg:grid-cols-[190px_1fr] xl:grid-cols-[190px_1fr_320px]'
            : 'lg:grid-cols-[44px_1fr] xl:grid-cols-[44px_1fr_320px]'
        }`}
      >
        {/* -------------------------------------------------- organ rail */}
        <nav className="hidden lg:flex flex-col border-r border-edge bg-panel
                        overflow-y-auto overflow-x-hidden">
          <button
            onClick={() => setRailOpen((v) => !v)}
            title={railOpen ? 'Collapse the organ rail' : 'Expand the organ rail'}
            aria-label={railOpen ? 'Collapse the organ rail' : 'Expand the organ rail'}
            aria-expanded={railOpen}
            className={`shrink-0 flex items-center border-b border-edge py-2.5
              text-slate-500 hover:text-slate-100 hover:bg-panel2 transition-colors ${
                railOpen ? 'px-3 gap-2 justify-between' : 'px-0 justify-center'
              }`}
          >
            {railOpen && <span className="label">Investigation organs</span>}
            <span className="font-mono text-[11px] leading-none">
              {railOpen ? '«' : '»'}
            </span>
          </button>
          {/* Locked until the trace has run. Every organ reads from the
              analysis, so before "Begin investigation" there is nothing behind
              any of them - and a button that highlights on click while the
              screen never changes reads as a frozen application, which is
              exactly how this looked. Saying "locked" is the fix; silently
              doing nothing was the bug. */}
          {ORGANS.map((o) => (
            <button
              key={o.id}
              onClick={() => setOrgan(o.id)}
              disabled={!data.started}
              title={data.started ? o.label
                                  : `${o.label} — begin the investigation to open this`}
              className={`flex items-center py-2 text-[11px] text-left
                border-l-2 transition-colors ${
                  railOpen ? 'gap-2.5 px-3' : 'justify-center px-0'
                } ${
                  !data.started
                    ? 'border-transparent text-slate-700 cursor-not-allowed'
                    : organ === o.id
                      ? 'border-violet bg-violet/10 text-slate-100'
                      : 'border-transparent text-slate-500 hover:text-slate-200 hover:bg-panel2'
                }`}
            >
              <span
                className={`w-3 text-center shrink-0 ${
                  data.started ? 'text-violet/70' : 'text-slate-700'
                }`}
              >
                {o.icon}
              </span>
              {railOpen && <span className="truncate">{o.label}</span>}
            </button>
          ))}
          {!data.started && railOpen && (
            <div className="px-3 py-2 text-[10px] leading-snug text-slate-600">
              Locked until the trace runs. Press
              <span className="text-violet-300"> Begin investigation</span>.
            </div>
          )}
          {/* Derived from the real evidence register: a file is "verified"
              only when the browser hash and the server hash actually agree.
              This previously read "SHA-256 chain valid" unconditionally - a
              false integrity claim in a forensics tool. */}
          <div className={`mt-auto border-t border-edge ${railOpen ? 'p-3' : 'py-2 px-0 text-center'}`}>
            {railOpen ? (
              <div className="label mb-1">Evidence integrity</div>
            ) : (
              /* Collapsed, the integrity state survives as a single mark. It is
                 the one thing on this rail that is a claim about the evidence
                 rather than a way to navigate, so it does not get hidden. */
              <div
                title={
                  evidence.length === 0
                    ? 'No files ingested'
                    : verified === evidence.length
                      ? `${verified}/${evidence.length} hash-verified`
                      : `${evidence.length - verified} of ${evidence.length} failed verification`
                }
                className={`font-mono text-[11px] ${
                  evidence.length === 0
                    ? 'text-slate-600'
                    : verified === evidence.length
                      ? 'text-risk-low'
                      : 'text-risk-critical'
                }`}
              >
                {evidence.length === 0 ? '–' : verified === evidence.length ? '✓' : '✗'}
              </div>
            )}
            {railOpen && (evidence.length === 0 ? (
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
            ))}
          </div>
        </nav>

        {/* ------------------------------------------------ working surface */}
        <main className="min-w-0 min-h-0 overflow-hidden bg-ground">
          {data.started ? main : (
            <Briefing
              kase={kase}
              evidence={evidence}
              running={data.running}
              error={data.error}
              onRun={investigate}
              user={session.user}
            />
          )}
        </main>

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
