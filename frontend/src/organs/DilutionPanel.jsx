/**
 * ORGAN 6 — Dilution Calculator ("How violet is this utensil?").  Owner: FE2
 *
 * Shows the proportional haircut with the arithmetic on screen. This is the
 * false-positive story: a wallet holding mostly clean liquidity falls below
 * the reporting threshold and is correctly NOT flagged.
 */

import { Empty } from '../components/ui'

function Bar({ ratio, flagged }) {
  return (
    <div className="h-1.5 bg-edge rounded overflow-hidden">
      <div
        className="h-full transition-all"
        style={{
          width: `${Math.max(2, ratio * 100)}%`,
          background: flagged ? '#e5484d' : '#3d9a6d',
        }}
      />
    </div>
  )
}

export default function DilutionPanel({ dilution, onSelect, selected }) {
  if (!dilution) return <Empty>No dilution data.</Empty>

  const rescue = [...dilution.steps].reverse().find((s) => !s.flagged)

  return (
    <div className="p-4 space-y-4 overflow-y-auto h-full">
      <div className="bg-panel2 rounded p-3">
        <div className="label mb-2">Proportional haircut</div>
        <pre className="font-mono text-[10px] text-slate-400 leading-relaxed
                        overflow-x-auto">
{`              incoming × source_ratio
new ratio =  ─────────────────────────
             prior_balance + incoming`}
        </pre>
      </div>

      {rescue && (
        <div className="rounded border border-risk-low/40 bg-risk-low/10 p-3">
          <div className="text-[10px] font-bold uppercase tracking-wider
                          text-risk-low mb-1.5">
            ✓ False positive avoided
          </div>
          <pre className="font-mono text-[10px] text-slate-300 leading-relaxed
                          overflow-x-auto">
{`dirty received = ${rescue.incoming_amount.toLocaleString('en-IN')} × ${rescue.incoming_ratio} = ${rescue.dirty_received.toLocaleString('en-IN')}
new ratio      = ${rescue.dirty_received.toLocaleString('en-IN')} / ${rescue.total_after.toLocaleString('en-IN')} = ${(rescue.illicit_ratio * 100).toFixed(0)}%`}
          </pre>
          <p className="text-[10px] text-slate-400 mt-2 leading-relaxed">
            Falls below the {(dilution.threshold * 100).toFixed(0)}% reporting
            threshold, so this wallet is <strong>not flagged</strong>. Clean
            liquidity pools are not incorrectly implicated.
          </p>
        </div>
      )}

      <div>
        <div className="label mb-2">
          Decay chain · {dilution.steps.length} transfers
        </div>
        <ul className="space-y-2">
          {dilution.steps.map((s, idx) => (
            <li
              key={`${s.node_id}-${idx}`}
              onClick={() => onSelect?.(s.node_id)}
              className={`cursor-pointer rounded px-2 py-1.5 transition-colors
                ${selected === s.node_id ? 'bg-violet/15' : 'hover:bg-panel2'}`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono text-[10px] text-slate-400 truncate flex-1">
                  {s.node_id.startsWith('0x')
                    ? `${s.node_id.slice(0, 10)}…${s.node_id.slice(-6)}`
                    : s.node_id}
                </span>
                <span
                  className="font-mono text-[11px] tabular-nums font-bold"
                  style={{ color: s.flagged ? '#e5484d' : '#3d9a6d' }}
                >
                  {(s.illicit_ratio * 100).toFixed(0)}%
                </span>
              </div>
              <Bar ratio={s.illicit_ratio} flagged={s.flagged} />
              <div className="mt-1 font-mono text-[9px] text-slate-600">
                {s.prior_balance.toLocaleString('en-IN')} prior +{' '}
                {s.incoming_amount.toLocaleString('en-IN')} in ·{' '}
                {s.dirty_received.toLocaleString('en-IN')} traced
              </div>
            </li>
          ))}
        </ul>
      </div>

      <div className="pt-2 border-t border-edge text-[10px] text-slate-600 leading-relaxed">
        <strong className="text-slate-500">Known limitation.</strong> The
        haircut model can be diluted deliberately by padding a wallet with clean
        funds. FIFO, LIFO and poison/taint trade off differently; poison
        over-flags severely. Haircut was chosen to minimise false positives.
      </div>
    </div>
  )
}
