/**
 * ORGAN 4 — Timeline.  Owner: FE1
 * Police evaluate a case sequentially. The deltas are the finding: a
 * 13-second gap between a UPI debit and an exchange deposit is evidence.
 */

import { ConfidenceTag, Empty, delta, timeIST } from '../components/ui'

const DOT = {
  bank: '#4a9d8e',
  onchain: '#8b6fd4',
  system: '#6b6579',
}

export default function Timeline({ timeline, selected, onSelect }) {
  if (!timeline?.length) return <Empty>No events reconstructed.</Empty>

  return (
    <div className="p-4 overflow-y-auto h-full">
      <ol className="relative border-l border-edge ml-2">
        {timeline.map((e) => {
          const inferred = e.event_type === 'inferred_correlation'
          const active = selected && e.node_id === selected
          return (
            <li
              key={e.event_id}
              onClick={() => onSelect?.(e.node_id)}
              className={`relative pl-4 pb-3 cursor-pointer group
                ${active ? 'bg-violet/10' : ''}`}
            >
              <i
                className="absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full
                           border-2 border-ground"
                style={{ background: DOT[e.source] ?? DOT.system }}
              />

              {e.delta_seconds_prev > 0 && (
                <div className="font-mono text-[9px] text-slate-600 mb-0.5">
                  {delta(e.delta_seconds_prev)}
                </div>
              )}

              <div className="flex items-baseline gap-2 flex-wrap">
                <span className="font-mono text-[11px] text-slate-300 tabular-nums">
                  {timeIST(e.timestamp)}
                </span>
                {inferred && <ConfidenceTag value="inferred" />}
              </div>

              <p
                className={`text-[11px] leading-snug mt-0.5
                  ${inferred ? 'text-[#d9b21c]' : 'text-slate-400'}
                  group-hover:text-slate-200`}
              >
                {e.description}
              </p>

              {e.edge_id && (
                <span className="font-mono text-[9px] text-slate-700">
                  {e.edge_id}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
