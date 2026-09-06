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

export default function AuditLog({ audit = [], verification }) {
  if (!audit.length) return <Empty>No recorded actions.</Empty>

  const intact = verification?.intact

  return (
    <div className="p-4 overflow-auto h-full space-y-3">
      {/* The chain is what turns "append-only by convention" into something
          a reader can check. Each entry commits to its predecessor. */}
      {verification && (
        <div
          className={`rounded border p-3 ${
            intact
              ? 'border-risk-low/40 bg-risk-low/10'
              : 'border-risk-critical/50 bg-risk-critical/10'
          }`}
        >
          <div
            className={`text-[10px] font-bold uppercase tracking-wider mb-1 ${
              intact ? 'text-risk-low' : 'text-risk-critical'
            }`}
          >
            {intact
              ? `✓ Chain intact · ${verification.entries} entries verified`
              : `✗ Chain broken at ${verification.broken_at}`}
          </div>
          <p className="text-[10px] text-slate-400 leading-relaxed">
            Every entry commits to the one before it, so editing, reordering or
            deleting any row breaks all subsequent links. This makes tampering
            detectable — it does not prevent it.
          </p>
          {intact && (
            <code className="block font-mono text-[9px] text-slate-500 break-all
                             mt-1.5">
              head {verification.head_hash}
            </code>
          )}
        </div>
      )}

      <div className="rounded border border-edge overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr>
              {['Timestamp', 'User', 'Action', 'Target', 'Evidence hash', 'Chain'].map((h) => (
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
                <td className="px-3 py-2 font-mono text-[10px] text-violet/70">
                  {a.entry_hash ? short(a.entry_hash, 8, 4) : '—'}
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
