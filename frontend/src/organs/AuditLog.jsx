/**
 * ORGAN 10 — Chain of Custody Audit Log.  Owner: FE1
 * Append-only. Every evidence interaction is bound to a hash and a timestamp
 * so the handling of the case can be reconstructed after the fact.
 */

import { Empty, short, timeIST, dateIST } from '../components/ui'

const ACTION_COLOR = {
  CASE_CREATED: '#5b8dd6',
  CASE_UPDATED: '#6b6579',
  EVIDENCE_UPLOADED: '#4a9d8e',
  TRACE_RUN: '#8b6fd4',
  RISK_COMPUTED: '#c9a227',
  DILUTION_COMPUTED: '#c9a227',
  REPORT_GENERATED: '#e5901d',
  MODE_SWITCHED: '#e5484d',
}

export default function AuditLog({ audit = [] }) {
  if (!audit.length) return <Empty>No recorded actions.</Empty>

  return (
    <div className="p-4 overflow-auto h-full">
      <div className="rounded border border-edge overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr>
              {['Timestamp', 'User', 'Action', 'Target', 'Hash'].map((h) => (
                <th
                  key={h}
                  className="label px-3 py-2 text-left whitespace-nowrap
                             border-b border-edge bg-panel2"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {audit.map((a) => (
              <tr key={a.audit_id} className="border-b border-edge/40 last:border-0">
                <td className="px-3 py-2 font-mono text-slate-500 whitespace-nowrap">
                  <span className="text-slate-300">{timeIST(a.timestamp)}</span>
                  <span className="text-slate-700">{' · '}{dateIST(a.timestamp)}</span>
                </td>
                <td className="px-3 py-2 font-mono text-slate-400 whitespace-nowrap">
                  {a.user_id}
                </td>
                <td className="px-3 py-2 whitespace-nowrap">
                  <span
                    className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded"
                    style={{
                      color: ACTION_COLOR[a.action] ?? '#6b6579',
                      background: `${ACTION_COLOR[a.action] ?? '#6b6579'}1a`,
                    }}
                  >
                    {a.action}
                  </span>
                </td>
                <td className="px-3 py-2 font-mono text-[10px] text-slate-500 max-w-[240px] truncate">
                  {a.target}
                </td>
                <td className="px-3 py-2 font-mono text-[10px] text-slate-600">
                  {a.target_hash ? short(a.target_hash, 10, 4) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-[10px] text-slate-600 mt-3 leading-relaxed max-w-2xl">
        This log is <strong className="text-slate-500">append-only</strong> —
        there is no update or delete path. An audit trail that can be edited is
        not an audit trail.
      </p>
    </div>
  )
}
