/**
 * ORGAN 3 — Graph Visualiser ("The Violet Milk Map").  Owner: FE2
 *
 * The single most important rendering rule: a `confirmed_*` edge is SOLID and
 * an `inferred_correlation` edge is DASHED. An inferred edge is a hypothesis -
 * a UPI debit and an exchange deposit 13 seconds apart - not a proven transfer.
 * Drawing the two identically would overstate the evidence, which is exactly
 * the failure a defence lawyer looks for.
 */

import { useEffect, useRef } from 'react'
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

const STYLE = [
  {
    selector: 'node',
    style: {
      'background-color': (n) => NODE_COLOR[n.data('type')] ?? '#6b6579',
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
      color: '#6b6579',
      'text-rotation': 'autorotate',
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
    spacingFactor: 1.4,
    ...(roots ? { roots } : {}),
  }
}

export default function GraphVisualiser({ graph, selected, onSelect }) {
  const boxRef = useRef(null)
  const cyRef = useRef(null)

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

    cy.on('tap', 'node', (evt) => onSelect?.(evt.target.id()))
    cy.on('tap', (evt) => {
      if (evt.target === cy) onSelect?.(null)
    })

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

  return (
    <div className="relative h-full min-h-[340px]">
      <div ref={boxRef} className="absolute inset-0" />

      <div className="absolute top-2 right-2 flex gap-1.5">
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

      <div className="absolute bottom-2 left-2 right-2 flex flex-wrap gap-x-4 gap-y-1
                      px-3 py-2 rounded bg-panel/95 border border-edge text-[10px]">
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
      </div>
    </div>
  )
}
