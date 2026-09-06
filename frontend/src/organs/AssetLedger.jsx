/**
 * ORGAN 11 — Asset Ledger ("what moved, and in what").
 *
 * Additive. Reads /api/cases/{id}/assets and shows currency composition
 * overall, per layer of the trace, and for the selected entity.
 *
 * The load-bearing detail: an asset with no rate renders as "no rate" in
 * muted type, NEVER as a rupee figure and never as zero. This build carries
 * no price feed, and a number here could end up quoted as a loss in a
 * chargesheet. The backend sends `convertible: false` for exactly this.
 */

import { RiskPill, short } from '../components/ui'

const ASSET_TONE = {
  INR: 'text-emerald-300 border-emerald-400/40 bg-emerald-400/10',
  USDT: 'text-violet-200 border-violet/40 bg-violet/10',
  ETH: 'text-sky-300 border-sky-400/40 bg-sky-400/10',
  TRX: 'text-rose-300 border-rose-400/40 bg-rose-400/10',
  TOKEN: 'text-amber-300 border-amber-400/40 bg-amber-400/10',
}

function AssetChip({ asset }) {
  const tone = ASSET_TONE[asset] || 'text-slate-300 border-edge bg-panel2'
  return (
    <span className={`inline-block px-1.5 py-px rounded border text-[10px]
                      font-mono tracking-wide ${tone}`}>
      {asset}
    </span>
  )
}

function Amount({ row }) {
  return (
    <div className="text-right tabular-nums">
      <div className="text-[12px] text-slate-200 font-mono">
        {row.total_amount.toLocaleString('en-IN', {
          maximumFractionDigits: row.asset === 'INR' ? 0 : 2,
        })}
      </div>
      <div className="text-[10px] font-mono">
        {row.convertible && row.inr_formatted ? (
          <span className="text-slate-500">₹{row.inr_formatted}</span>
        ) : (
          <span className="text-slate-600 italic">no rate</span>
        )}
      </div>
    </div>
  )
}

function AssetRows({ rows, empty = '—' }) {
  if (!rows || rows.length === 0) {
    return <div className="text-[11px] text-slate-600 italic">{empty}</div>
  }
  return (
    <div className="flex flex-col gap-1">
      {rows.map((r) => (
        <div key={r.asset} className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AssetChip asset={r.asset} />
            <span className="text-[10px] text-slate-500 font-mono">
              {r.transfer_count} tx
            </span>
          </div>
          <Amount row={r} />
        </div>
      ))}
    </div>
  )
}

export default function AssetLedger({ assets, selected, nodesById }) {
  if (!assets) {
    return (
      <div className="p-6 text-[12px] text-slate-500">
        Asset ledger unavailable. The rest of the case is unaffected — this
        panel is derived from the same traced graph and carries no evidence of
        its own.
      </div>
    )
  }

  const node = selected
    ? assets.nodes.find((n) => n.node_id.toLowerCase() === selected.toLowerCase())
    : null

  return (
    <div className="h-full overflow-y-auto p-4 flex flex-col gap-5">

      {/* ------------------------------------------------------- totals */}
      <section>
        <div className="label mb-2">Currency moved · whole case</div>
        <div className="grid gap-2 sm:grid-cols-2">
          {assets.totals.map((t) => (
            <div key={t.asset}
                 className="border border-edge rounded bg-panel2 px-3 py-2.5">
              <div className="flex items-center justify-between mb-1.5">
                <AssetChip asset={t.asset} />
                <span className="text-[10px] text-slate-500 font-mono">
                  {t.transfer_count} transfers
                </span>
              </div>
              <div className="text-[17px] text-slate-100 font-mono tabular-nums">
                {t.total_amount.toLocaleString('en-IN', {
                  maximumFractionDigits: t.asset === 'INR' ? 0 : 2,
                })}
              </div>
              <div className="text-[11px] font-mono mt-0.5">
                {t.convertible && t.inr_formatted ? (
                  <span className="text-slate-400">₹{t.inr_formatted}</span>
                ) : (
                  <span className="text-slate-600 italic">
                    no rate in this build
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------------- layers */}
      <section>
        <div className="label mb-2">
          Composition by layer · {assets.layers.length} depths
        </div>
        <div className="flex flex-col">
          {assets.layers.map((l) => (
            <div key={l.depth}
                 className="grid grid-cols-[auto_1fr] gap-3 py-2.5
                            border-b border-edge last:border-b-0">
              <div className="w-20">
                <div className="text-[11px] text-violet font-mono">
                  depth {l.depth}
                </div>
                <div className="text-[10px] text-slate-600 font-mono">
                  {l.node_count} {l.node_count === 1 ? 'entity' : 'entities'}
                </div>
                {l.depth === 0 && (
                  <div className="text-[9px] text-slate-600 mt-0.5">seed</div>
                )}
              </div>
              <AssetRows rows={l.assets} />
            </div>
          ))}
        </div>
        <p className="text-[10px] text-slate-600 mt-2 leading-relaxed">
          A transfer is counted at the depth of the entity that received it, so
          each layer reads as “what arrived here”.
        </p>
      </section>

      {/* -------------------------------------------------- selected node */}
      <section>
        <div className="label mb-2">Selected entity</div>
        {!node ? (
          <div className="text-[11px] text-slate-600 italic">
            Select an entity in the graph to see what it received and sent.
          </div>
        ) : (
          <div className="border border-edge rounded bg-panel2 px-3 py-2.5">
            <div className="flex items-center justify-between gap-2 mb-2">
              <div className="font-mono text-[12px] text-slate-200">
                {short(node.node_id)}
              </div>
              <span className="text-[10px] text-slate-500 font-mono">
                depth {node.depth} · {node.node_type}
              </span>
            </div>
            {node.label && (
              <div className="text-[11px] text-slate-400 mb-2">{node.label}</div>
            )}
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <div className="label mb-1">Received</div>
                <AssetRows rows={node.received} empty="nothing inbound" />
              </div>
              <div>
                <div className="label mb-1">Sent</div>
                <AssetRows rows={node.sent} empty="nothing outbound" />
              </div>
            </div>
          </div>
        )}
      </section>

      {/* ------------------------------------------------------- caveat */}
      <section className="border-t border-edge pt-3">
        <div className="label mb-1">Conversion basis</div>
        <p className="text-[10px] text-slate-500 leading-relaxed">
          {assets.caveat}
        </p>
      </section>

    </div>
  )
}
