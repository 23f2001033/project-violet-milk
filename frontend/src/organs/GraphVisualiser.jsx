/**
 * ORGAN 3 — Graph Visualiser ("The Violet Milk Map").  Owner: FE2
 *
 * The single most important rendering rule: a `confirmed_*` edge is SOLID and
 * an `inferred_correlation` edge is DASHED. An inferred edge is a hypothesis -
 * a UPI debit and an exchange deposit 13 seconds apart - not a proven transfer.
 * Drawing the two identically would overstate the evidence, which is exactly
 * the failure a defence lawyer looks for.
 *
 * WHAT THE CARD IS FOR
 * --------------------
 * An officer looking at a wallet needs four things they can act on the same
 * morning: the full address to paste into a Section 94 BNSS notice, a link to
 * verify it on a public explorer without taking our word for anything, the
 * illicit share to attach to a freeze request, and the amounts by currency.
 * A hex string floating on a canvas is a picture; the card is the part that
 * does police work.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import { riskColor } from '../api'

const NODE_COLOR = {
  victim: '#5b8dd6',
  bank_account: '#4a9d8e',
  upi_handle: '#4a9d8e',
  exchange: '#c9a227',
  wallet: '#8b6fd4',
  mixer: '#e5484d',
  bridge: '#e5901d',
  contract: '#6b6579',
  unknown: '#6b6579',
}

// Shape carries entity type independently of colour, so the graph still reads
// on a projector that washes colour out, and for anyone colour-blind.
const NODE_SHAPE = {
  victim: 'star',
  bank_account: 'round-rectangle',
  upi_handle: 'round-rectangle',
  exchange: 'diamond',
  mixer: 'hexagon',
  bridge: 'hexagon',
  wallet: 'ellipse',
  contract: 'round-rectangle',
  unknown: 'ellipse',
}

const TYPE_LABEL = {
  victim: 'Complainant',
  bank_account: 'Bank account',
  upi_handle: 'UPI handle',
  exchange: 'Exchange',
  wallet: 'Wallet',
  mixer: 'Mixer',
  bridge: 'Bridge',
  contract: 'Contract',
  unknown: 'Unknown',
}

/* An officer must be able to check our claim against a public source. Only
   chains we actually trace get a link - never a guessed explorer URL. */
function explorerFor(id, chain) {
  if (chain === 'ethereum') return `https://etherscan.io/address/${id}`
  if (chain === 'tron') return `https://tronscan.org/#/address/${id}`
  return null
}

const shortId = (id) =>
  id.startsWith('0x') ? `${id.slice(0, 8)}…${id.slice(-6)}` : id

const STYLE = [
  {
    selector: 'node',
    style: {
      'background-color': (n) => NODE_COLOR[n.data('type')] ?? '#6b6579',
      shape: (n) => NODE_SHAPE[n.data('type')] ?? 'ellipse',
      label: 'data(short)',
      color: '#cbd5e1',
      'font-size': 9,
      'font-family': 'JetBrains Mono, monospace',
      'text-valign': 'bottom',
      'text-margin-y': 5,
      'text-background-color': '#0d0b12',
      'text-background-opacity': 0.75,
      'text-background-padding': 2,
      width: (n) => 18 + (n.data('risk_score') / 100) * 22,
      height: (n) => 18 + (n.data('risk_score') / 100) * 22,
      'border-width': 2,
      'border-color': (n) => riskColor(n.data('risk_level')),
      'transition-property': 'opacity, border-width',
      'transition-duration': '160ms',
    },
  },
  {
    selector: 'node[?is_seed]',
    style: { 'border-width': 4, 'border-color': '#ffffff' },
  },
  {
    selector: 'node:selected',
    style: { 'border-width': 4, 'border-color': '#c4b5fd' },
  },
  {
    selector: 'edge',
    style: {
      width: (e) => 1 + Math.min(4, Math.log10(e.data('amount') + 10)),
      'line-color': '#3e3950',
      'target-arrow-color': '#3e3950',
      'target-arrow-shape': 'triangle',
      'arrow-scale': 0.8,
      'curve-style': 'bezier',
      label: 'data(caption)',
      'font-size': 8,
      'font-family': 'JetBrains Mono, monospace',
      color: '#8b8496',
      'text-rotation': 'autorotate',
      // Amounts sat directly on top of crossing edges and each other. A plate
      // behind the text is what makes them readable on a busy graph.
      'text-background-color': '#0d0b12',
      'text-background-opacity': 0.82,
      'text-background-padding': 2,
      'text-background-shape': 'roundrectangle',
      'transition-property': 'opacity, line-color, width',
      'transition-duration': '160ms',
    },
  },
  {
    // The whole point: inferred links must never look like proven ones.
    selector: 'edge[evidence_type = "inferred_correlation"]',
    style: {
      'line-style': 'dashed',
      'line-color': '#d9b21c',
      'target-arrow-color': '#d9b21c',
      color: '#d9b21c',
    },
  },
  {
    selector: 'edge[evidence_type = "confirmed_bank"]',
    style: { 'line-color': '#4a9d8e', 'target-arrow-color': '#4a9d8e' },
  },
  {
    selector: 'edge:selected',
    style: { 'line-color': '#c4b5fd', 'target-arrow-color': '#c4b5fd' },
  },

  /* ---- follow-the-money highlighting -------------------------------- */
  {
    selector: '.dimmed',
    style: { opacity: 0.12, 'text-opacity': 0 },
  },
  {
    selector: 'node.on-path',
    style: { 'border-width': 4, 'border-color': '#f0abfc', opacity: 1 },
  },
  {
    selector: 'edge.on-path',
    style: {
      'line-color': '#f0abfc',
      'target-arrow-color': '#f0abfc',
      color: '#f0abfc',
      width: 3.5,
      opacity: 1,
      'z-index': 20,
    },
  },
  {
    selector: 'node.hovered',
    style: { 'border-width': 5, 'border-color': '#e9d5ff' },
  },
]

/**
 * Layout is chosen by shape, not by preference.
 *
 * A curated case is a chain: victim -> bank -> exchange -> wallet -> fan-out,
 * and breadthfirst renders that story left to right exactly as an officer
 * describes it.
 *
 * A live mainnet address is hub-and-spoke: one wallet with dozens of
 * counterparties. Breadthfirst lays those out in a single enormous row, and
 * fitting it to the pane shrinks every node to a speck - the canvas looked
 * blank. Concentric puts the seed at the centre with counterparties ringed
 * around it, which is both readable and an honest picture of the topology.
 */
function layoutFor(graph) {
  const nodes = graph.elements.nodes
  const common = { padding: 30, fit: true, animate: false }

  if (nodes.length > 25) {
    return {
      ...common,
      name: 'concentric',
      minNodeSpacing: 14,
      // Seed at the centre; everything else ranked by risk so the entities
      // that matter sit on the inner rings.
      concentric: (n) => (n.data('is_seed') ? 1000 : n.data('risk_score') || 1),
      levelWidth: () => 25,
    }
  }

  const victims = nodes.filter((n) => n.data.type === 'victim').map((n) => n.data.id)
  const seed = nodes.find((n) => n.data.is_seed)
  const roots = victims.length ? victims : seed ? [seed.data.id] : undefined

  return {
    ...common,
    name: 'breadthfirst',
    directed: true,
    spacingFactor: 1.75,
    // Without this the layout packs rows to the node circles and ignores the
    // address captions hanging below them, which is what made the lower ranks
    // read as a wall of overlapping text.
    nodeDimensionsIncludeLabels: true,
    avoidOverlap: true,
    ...(roots ? { roots } : {}),
  }
}

/**
 * Second pass that turns the ranked rows into the spread an officer can read.
 *
 * Breadthfirst alone is the right STORY - victim at the top, money falling
 * down the page - but it packs every entity at the same depth into one tight
 * row, so on the demo case the lower two ranks collide and the amount labels
 * pile on top of each other. A force pass started FROM those rows keeps the
 * top-to-bottom order while pushing entities apart into open canvas.
 *
 * `randomize: false` is the load-bearing option: cose then refines the
 * breadthfirst positions instead of seeding from Math.random, so the graph
 * lands identically every single run. A demo that lays out differently each
 * time cannot be rehearsed, and a forensic tool that draws the same case two
 * ways invites the obvious question about what else is non-deterministic.
 */
const SPREAD = {
  name: 'cose',
  animate: false,
  fit: true,
  padding: 38,
  randomize: false,
  nodeDimensionsIncludeLabels: true,
  idealEdgeLength: 125,
  nodeRepulsion: 15000,
  edgeElasticity: 110,
  gravity: 0.28,
  numIter: 1200,
  initialTemp: 180,
  coolingFactor: 0.95,
  minTemp: 1.0,
}

/**
 * Shortest route the money took from the complainant (or the seed, on a live
 * trace where there is no complainant) to the selected entity.
 *
 * Breadth-first along edge DIRECTION - the answer to "how did funds get here",
 * which is not the same question as "what is this connected to".
 */
function pathTo(graph, targetId) {
  if (!targetId) return null
  const nodes = graph.elements.nodes
  const start =
    nodes.find((n) => n.data.type === 'victim')?.data.id ??
    nodes.find((n) => n.data.is_seed)?.data.id
  if (!start || start === targetId) return null

  const out = new Map()
  for (const e of graph.elements.edges) {
    if (!out.has(e.data.source)) out.set(e.data.source, [])
    out.get(e.data.source).push(e.data)
  }

  const prev = new Map()
  const seen = new Set([start])
  let frontier = [start]

  while (frontier.length) {
    const next = []
    for (const id of frontier) {
      for (const e of out.get(id) ?? []) {
        if (seen.has(e.target)) continue
        seen.add(e.target)
        prev.set(e.target, { from: id, edge: e.id })
        if (e.target === targetId) {
          const nodeIds = [targetId]
          const edgeIds = []
          let cur = targetId
          while (prev.has(cur)) {
            const step = prev.get(cur)
            edgeIds.push(step.edge)
            nodeIds.push(step.from)
            cur = step.from
          }
          return { nodes: nodeIds.reverse(), edges: edgeIds.reverse() }
        }
        next.push(e.target)
      }
    }
    frontier = next
  }
  return null
}

/* ------------------------------------------------------------------ card */

function Row({ k, v, mono = false, tone = 'text-slate-200' }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-[3px]">
      <span className="text-[9.5px] uppercase tracking-wider text-slate-500 shrink-0">
        {k}
      </span>
      <span className={`text-[11px] text-right ${tone} ${mono ? 'font-mono' : ''}`}>
        {v}
      </span>
    </div>
  )
}

function AssetLine({ rows, empty }) {
  if (!rows?.length) {
    return <div className="text-[10px] text-slate-600 italic">{empty}</div>
  }
  return (
    <div className="flex flex-col gap-[2px]">
      {rows.map((r) => (
        <div key={r.asset} className="flex items-baseline justify-between gap-2">
          <span className="text-[10px] font-mono text-slate-400">{r.asset}</span>
          <span className="text-[10.5px] font-mono text-slate-200 tabular-nums">
            {r.total_amount.toLocaleString('en-IN', {
              maximumFractionDigits: r.asset === 'INR' ? 0 : 2,
            })}
            {r.convertible && r.inr_formatted ? (
              <span className="text-slate-500"> · ₹{r.inr_formatted}</span>
            ) : (
              <span className="text-slate-600 italic"> · no rate</span>
            )}
          </span>
        </div>
      ))}
    </div>
  )
}

function WalletCard({
  node, assets, risk, path, onClose, onFollow, following, maxHeight,
}) {
  const [copied, setCopied] = useState(false)
  const explorer = explorerFor(node.id, node.chain)
  const ledger = assets?.nodes?.find(
    (n) => n.node_id.toLowerCase() === node.id.toLowerCase()
  )

  const copy = () => {
    navigator.clipboard?.writeText(node.id).then(
      () => {
        setCopied(true)
        setTimeout(() => setCopied(false), 1600)
      },
      () => setCopied(false)
    )
  }

  return (
    <div
      style={{ maxHeight }}
      className="absolute top-2 left-2 w-[292px] overflow-y-auto
                 rounded border border-edge bg-panel/97 backdrop-blur shadow-xl
                 text-slate-300"
    >
      {/* header */}
      <div className="flex items-start gap-2 px-3 pt-2.5 pb-2 border-b border-edge">
        <i
          className="w-2.5 h-2.5 rounded-full mt-1 shrink-0"
          style={{ background: NODE_COLOR[node.type] ?? '#6b6579' }}
        />
        <div className="min-w-0 flex-1">
          <div className="text-[11px] text-slate-100 font-medium leading-tight">
            {node.label || TYPE_LABEL[node.type] || 'Unknown entity'}
          </div>
          <div className="text-[9.5px] text-slate-500 uppercase tracking-wider mt-0.5">
            {TYPE_LABEL[node.type] ?? node.type}
            {node.is_seed && ' · case seed'}
          </div>
        </div>
        <button
          onClick={onClose}
          aria-label="Close entity card"
          className="text-slate-500 hover:text-slate-200 text-[13px] leading-none px-1"
        >
          ×
        </button>
      </div>

      {/* address */}
      <div className="px-3 py-2 border-b border-edge">
        <div className="text-[9.5px] uppercase tracking-wider text-slate-500 mb-1">
          Address
        </div>
        <div className="font-mono text-[10px] text-slate-200 break-all leading-relaxed">
          {node.id}
        </div>
        <div className="flex gap-1.5 mt-2">
          <button
            onClick={copy}
            className="px-2 py-1 text-[9.5px] font-mono rounded border border-edge
                       text-slate-300 hover:text-slate-100 hover:border-violet/60"
          >
            {copied ? '✓ COPIED' : 'COPY'}
          </button>
          {explorer && (
            <a
              href={explorer}
              target="_blank"
              rel="noreferrer noopener"
              className="px-2 py-1 text-[9.5px] font-mono rounded border border-edge
                         text-slate-300 hover:text-slate-100 hover:border-violet/60"
            >
              VERIFY ↗
            </a>
          )}
          <button
            onClick={onFollow}
            disabled={!path}
            title={path ? 'Highlight the route funds took to reach here'
                        : 'No inbound route from the complainant'}
            className={`px-2 py-1 text-[9.5px] font-mono rounded border
              ${following
                ? 'border-fuchsia-400/70 text-fuchsia-300'
                : 'border-edge text-slate-300 hover:text-slate-100 hover:border-violet/60'}
              disabled:opacity-35 disabled:cursor-not-allowed`}
          >
            {following ? 'TRACKING' : 'FOLLOW'}
          </button>
        </div>
      </div>

      {/* assessment */}
      <div className="px-3 py-2 border-b border-edge">
        <div className="flex items-center gap-3">
          <div
            className="w-11 h-11 rounded-full grid place-items-center shrink-0
                       border-2 font-mono"
            style={{ borderColor: riskColor(node.risk_level) }}
          >
            <span className="text-[14px] text-slate-100 leading-none">
              {node.risk_score}
            </span>
          </div>
          <div className="min-w-0">
            <div
              className="text-[11px] font-medium"
              style={{ color: riskColor(node.risk_level) }}
            >
              {node.risk_level}
            </div>
            <div className="text-[9.5px] text-slate-500">
              deterministic · 7 rules
            </div>
          </div>
          <div className="ml-auto text-right">
            <div className="text-[9.5px] uppercase tracking-wider text-slate-500">
              Illicit
            </div>
            <div className="text-[14px] font-mono text-slate-100">
              {Math.round((node.illicit_ratio ?? 0) * 100)}%
            </div>
          </div>
        </div>

        {risk?.indicators?.length > 0 && (
          <div className="mt-2 flex flex-col gap-1">
            {risk.indicators.map((i) => (
              <div key={i.rule_id} className="flex gap-1.5 items-baseline">
                <span className="text-[9px] font-mono text-violet shrink-0">
                  {i.rule_id}
                </span>
                <span className="text-[9px] font-mono text-amber-300 shrink-0">
                  +{i.points}
                </span>
                <span className="text-[9.5px] text-slate-400 leading-snug">
                  {i.name}
                </span>
              </div>
            ))}
          </div>
        )}
        {risk && risk.indicators?.length === 0 && (
          <div className="mt-2 text-[9.5px] text-slate-500 italic">
            No rule fired on this entity.
          </div>
        )}
      </div>

      {/* money */}
      <div className="px-3 py-2 border-b border-edge">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="text-[9.5px] uppercase tracking-wider text-slate-500 mb-1">
              Received
            </div>
            <AssetLine rows={ledger?.received} empty="nothing inbound" />
          </div>
          <div>
            <div className="text-[9.5px] uppercase tracking-wider text-slate-500 mb-1">
              Sent
            </div>
            <AssetLine rows={ledger?.sent} empty="nothing outbound" />
          </div>
        </div>
      </div>

      {/* provenance */}
      <div className="px-3 py-2">
        <Row k="Chain" v={node.chain} mono />
        {ledger && <Row k="Layer" v={`depth ${ledger.depth}`} mono />}
        <Row
          k="Attribution"
          v={node.label ? node.label_confidence : 'unknown'}
          mono
          tone={node.label ? 'text-slate-200' : 'text-slate-500'}
        />
        {!node.label && (
          <p className="text-[9px] text-slate-600 leading-relaxed mt-1">
            No label on record. Unlabelled is <em>unknown</em>, not clean.
          </p>
        )}
      </div>
    </div>
  )
}

/* ----------------------------------------------------------------- organ */

export default function GraphVisualiser({ graph, selected, onSelect, assets, risk }) {
  const boxRef = useRef(null)
  const cyRef = useRef(null)
  const [hover, setHover] = useState(null)
  const [following, setFollowing] = useState(false)
  const [minRisk, setMinRisk] = useState(0)
  const [showCard, setShowCard] = useState(true)
  const [legendOpen, setLegendOpen] = useState(true)

  /* The legend used to span the full width at the bottom, so an open entity
     card ran underneath it and its last rows - chain, layer, attribution -
     were unreadable. Everything anchored to the bottom now measures from one
     number, and the card is bounded by it rather than overlapping it. */
  const legendH = legendOpen ? 78 : 32

  const nodesById = useMemo(() => {
    const m = {}
    for (const n of graph?.elements?.nodes ?? []) m[n.data.id] = n.data
    return m
  }, [graph])

  const path = useMemo(
    () => (graph && selected ? pathTo(graph, selected) : null),
    [graph, selected]
  )

  useEffect(() => {
    if (!boxRef.current || !graph) return

    const elements = [
      ...graph.elements.nodes.map((n) => ({
        data: {
          ...n.data,
          short: n.data.id.startsWith('0x')
            ? `${n.data.id.slice(0, 6)}…${n.data.id.slice(-4)}`
            : n.data.id,
        },
      })),
      ...graph.elements.edges.map((e) => ({
        data: {
          ...e.data,
          caption: `${e.data.amount.toLocaleString('en-IN')} ${e.data.asset}`,
        },
      })),
    ]

    const cy = cytoscape({
      container: boxRef.current,
      elements,
      style: STYLE,
      layout: layoutFor(graph),
      wheelSensitivity: 0.2,
      minZoom: 0.2,
      maxZoom: 2.5,
    })

    // Relax the ranked rows apart. Only for the case-sized graph: the live
    // concentric layout is already readable and a force pass on 50+ hub-and-
    // spoke nodes drifts into a hairball.
    if (graph.elements.nodes.length <= 25) {
      cy.layout(SPREAD).run()
    }

    cy.on('tap', 'node', (evt) => {
      setShowCard(true)
      onSelect?.(evt.target.id())
    })
    cy.on('tap', (evt) => {
      if (evt.target === cy) onSelect?.(null)
    })
    cy.on('mouseover', 'node', (evt) => setHover(evt.target.id()))
    cy.on('mouseout', 'node', () => setHover(null))

    // Cytoscape measures its container at construction time. Inside a CSS grid
    // the final width is not settled yet, so the first layout is computed
    // against a near-zero box and the graph renders clipped off-canvas.
    // Re-fitting once the element has real dimensions is what makes it usable.
    const refit = () => {
      cy.resize()
      cy.fit(undefined, 30)
    }
    // `ready` fires before the layout has finished positioning nodes, so
    // fitting there centres on half-placed coordinates and leaves the graph
    // hugging one edge. `layoutstop` is the point at which positions are final.
    cy.on('layoutstop', refit)
    cy.ready(() => cy.resize())

    // Fit is timing-sensitive in a way that is not worth being clever about.
    // `layoutstop` can fire during construction, before this handler exists;
    // the three-column grid may still be resolving track widths; and fonts
    // load asynchronously. Any single hook leaves a case where the graph
    // renders pinned to one edge and reads as broken. A few cheap settling
    // passes cover all of them - the manual FIT control proved the fit itself
    // is correct, only its timing was wrong.
    const settles = [80, 300, 800].map((ms) => setTimeout(refit, ms))

    const ro = new ResizeObserver(refit)
    ro.observe(boxRef.current)

    cyRef.current = cy
    return () => {
      settles.forEach(clearTimeout)
      ro.disconnect()
      cy.destroy()
    }
  }, [graph, onSelect])

  // Selection is driven from outside so the Timeline and Risk Inspector stay
  // in sync with the canvas.
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.$(':selected').unselect()
    if (!selected) return

    const node = cy.getElementById(selected)
    if (node.empty()) return
    node.select()

    // Only pan when the node is actually off-screen. Centring unconditionally
    // fought the initial fit: selecting the seed straight after a trace panned
    // the view to the edge of the layout and pushed the rest of the graph out
    // of sight, which read as a broken render.
    const view = cy.extent()
    const p = node.position()
    const inView =
      p.x > view.x1 && p.x < view.x2 && p.y > view.y1 && p.y < view.y2
    if (!inView) cy.animate({ center: { eles: node } }, { duration: 220 })
  }, [selected])

  // Hover emphasis, kept out of the constructor so it never re-runs a layout.
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.batch(() => {
      cy.nodes().removeClass('hovered')
      if (hover) cy.getElementById(hover).addClass('hovered')
    })
  }, [hover])

  /* Follow-the-money and the risk filter both work by dimming, never by
     removing elements. Hiding a node would quietly change the picture an
     officer is reading; dimming keeps the whole graph on screen and honest. */
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return

    cy.batch(() => {
      cy.elements().removeClass('dimmed on-path')

      if (following && path) {
        const keepN = new Set(path.nodes)
        const keepE = new Set(path.edges)
        cy.nodes().forEach((n) => {
          if (keepN.has(n.id())) n.addClass('on-path')
          else n.addClass('dimmed')
        })
        cy.edges().forEach((e) => {
          if (keepE.has(e.id())) e.addClass('on-path')
          else e.addClass('dimmed')
        })
        return
      }

      if (minRisk > 0) {
        cy.nodes().forEach((n) => {
          if ((n.data('risk_score') ?? 0) < minRisk && !n.data('is_seed')) {
            n.addClass('dimmed')
          }
        })
        cy.edges().forEach((e) => {
          const a = cy.getElementById(e.data('source'))
          const b = cy.getElementById(e.data('target'))
          if (a.hasClass('dimmed') || b.hasClass('dimmed')) e.addClass('dimmed')
        })
      }
    })
  }, [following, path, minRisk, graph])

  // A path that no longer exists must not leave the canvas dimmed.
  useEffect(() => {
    if (!path) setFollowing(false)
  }, [path])

  const node = selected ? nodesById[selected] : null
  const hovered = hover ? nodesById[hover] : null

  return (
    <div className="relative h-full min-h-[340px]">
      <div ref={boxRef} className="absolute inset-0" />

      {node && showCard && (
        <WalletCard
          node={node}
          assets={assets}
          risk={risk}
          path={path}
          following={following}
          onFollow={() => setFollowing((v) => !v)}
          onClose={() => setShowCard(false)}
          maxHeight={`calc(100% - ${legendH + 20}px)`}
        />
      )}

      {/* Hover read-out. Deliberately not a floating tooltip: one that chases
          the cursor across a projected canvas is unreadable from the back of
          a room. A fixed strip in a known place is not. */}
      {hovered && hovered.id !== selected && (
        <div className="absolute top-2 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded
                        border border-edge bg-panel/95 flex items-center gap-2.5
                        pointer-events-none">
          <i
            className="w-2 h-2 rounded-full"
            style={{ background: NODE_COLOR[hovered.type] ?? '#6b6579' }}
          />
          <span className="font-mono text-[10px] text-slate-200">
            {shortId(hovered.id)}
          </span>
          <span className="text-[10px] text-slate-500">
            {TYPE_LABEL[hovered.type] ?? hovered.type}
          </span>
          <span
            className="text-[10px] font-mono"
            style={{ color: riskColor(hovered.risk_level) }}
          >
            {hovered.risk_score}
          </span>
          <span className="text-[10px] text-slate-500">
            {Math.round((hovered.illicit_ratio ?? 0) * 100)}% illicit
          </span>
        </div>
      )}

      <div className="absolute top-2 right-2 flex flex-col items-end gap-1.5">
        <div className="flex gap-1.5">
          {node && !showCard && (
            <button
              onClick={() => setShowCard(true)}
              className="px-2 py-1 text-[10px] font-mono rounded border border-violet/50
                         bg-panel/90 text-violet-200 hover:text-slate-100"
            >
              CARD
            </button>
          )}
          <button
            onClick={() => cyRef.current?.fit(undefined, 30)}
            className="px-2 py-1 text-[10px] font-mono rounded border border-edge
                       bg-panel/90 text-slate-400 hover:text-slate-100"
          >
            FIT
          </button>
          <button
            onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 1.25)}
            className="px-2 py-1 text-[10px] font-mono rounded border border-edge
                       bg-panel/90 text-slate-400 hover:text-slate-100"
          >
            +
          </button>
          <button
            onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 0.8)}
            className="px-2 py-1 text-[10px] font-mono rounded border border-edge
                       bg-panel/90 text-slate-400 hover:text-slate-100"
          >
            −
          </button>
        </div>

        <div className="flex items-center gap-2 px-2 py-1 rounded border border-edge
                        bg-panel/90">
          <span className="text-[9.5px] uppercase tracking-wider text-slate-500">
            Risk ≥
          </span>
          <input
            type="range"
            min="0"
            max="80"
            step="10"
            value={minRisk}
            onChange={(e) => setMinRisk(Number(e.target.value))}
            disabled={following}
            aria-label="Dim entities below this risk score"
            className="w-20 accent-violet disabled:opacity-40"
          />
          <span className="text-[10px] font-mono text-slate-300 w-5 tabular-nums">
            {minRisk}
          </span>
        </div>
      </div>

      {following && path && (
        <div
          style={{ bottom: legendH + 10 }}
          className="absolute left-2 px-3 py-1.5 rounded border
                     border-fuchsia-400/50 bg-panel/95 text-[10px]
                     text-fuchsia-300 font-mono"
        >
          Route from complainant · {path.nodes.length} entities ·{' '}
          {path.edges.length} transfers
        </div>
      )}

      {legendOpen ? (
        <div className="absolute bottom-2 left-2 right-2 flex flex-wrap items-center
                        gap-x-4 gap-y-1 pl-3 pr-1 py-2 rounded bg-panel/95
                        border border-edge text-[10px]">
          {Object.entries({
            Victim: NODE_COLOR.victim,
            Bank: NODE_COLOR.bank_account,
            Exchange: NODE_COLOR.exchange,
            Wallet: NODE_COLOR.wallet,
            Mixer: NODE_COLOR.mixer,
            Bridge: NODE_COLOR.bridge,
          }).map(([k, v]) => (
            <span key={k} className="flex items-center gap-1.5 text-slate-400">
              <i className="w-2 h-2 rounded-full" style={{ background: v }} />
              {k}
            </span>
          ))}
          <span className="flex items-center gap-1.5 text-slate-400 ml-auto">
            <i className="w-5 h-px bg-slate-500" /> confirmed
          </span>
          <span className="flex items-center gap-1.5 text-[#d9b21c]">
            <i
              className="w-5 h-px"
              style={{
                backgroundImage:
                  'repeating-linear-gradient(90deg,#d9b21c 0 3px,transparent 3px 6px)',
              }}
            />
            inferred
          </span>
          <button
            onClick={() => setLegendOpen(false)}
            aria-label="Hide legend"
            title="Hide legend"
            className="ml-1 px-1.5 py-0.5 rounded text-slate-500 hover:text-slate-100
                       hover:bg-panel2 text-[11px] leading-none"
          >
            ▾
          </button>
        </div>
      ) : (
        <button
          onClick={() => setLegendOpen(true)}
          aria-label="Show legend"
          title="Show legend"
          className="absolute bottom-2 left-2 px-2 py-1 rounded border border-edge
                     bg-panel/90 text-[10px] font-mono text-slate-400
                     hover:text-slate-100 flex items-center gap-1.5"
        >
          <i className="w-2 h-2 rounded-full" style={{ background: NODE_COLOR.wallet }} />
          LEGEND ▴
        </button>
      )}
    </div>
  )
}
