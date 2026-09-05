/**
 * ORGAN 7 — Court Dossier Exporter.  Owner: FE2
 *
 * The Report Engine lands in Phase 5. The contract is already frozen, so this
 * organ is wired against the real shape and surfaces the 501 honestly rather
 * than faking a download.
 */

import { useState } from 'react'
import { Button } from '../components/ui'
import { generateReport } from '../api'

const SECTIONS = [
  ['Agency header & case metadata', 'FIR / NCRP reference, IO, incident time'],
  ['Section 63 BSA 2023 certificate', 'Statutory electronic-evidence certificate'],
  ['Evidence hash table', 'SHA-256 for every ingested file, client and server'],
  ['Graph & timeline snapshot', 'Confirmed and inferred links listed separately'],
  ['Risk & dilution appendix', 'Every indicator with its evidence and engine version'],
  ['Limitations', 'What this analysis does not establish'],
  ['Document SHA-256 & DSC block', 'Hash of the dossier itself, plus IO signature'],
]

export default function ReportExport({ kase }) {
  const [state, setState] = useState({ status: 'idle' })

  async function run() {
    setState({ status: 'working' })
    try {
      const r = await generateReport(kase.case_id)
      setState({ status: 'done', result: r })
    } catch (e) {
      setState({ status: 'error', error: e.message })
    }
  }

  return (
    <div className="p-5 overflow-y-auto h-full">
      <div className="max-w-2xl space-y-4">
        <div className="organ p-4">
          <div className="text-center border-b border-edge pb-3 mb-3">
            <div className="text-[11px] tracking-[0.18em] text-slate-300 font-bold">
              CHANDIGARH POLICE CYBER CRIME UNIT
            </div>
            <div className="text-[10px] text-violet mt-1 tracking-wider">
              ELECTRONIC EVIDENCE DOSSIER · SEC 63 BSA 2023
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[11px]">
            {[
              ['Case reference', kase.case_id],
              ['FIR / NCRP', kase.ncrp_ref],
              ['Target wallet', kase.seed_wallet],
              ['Investigating officer', kase.io_name],
            ].map(([k, v]) => (
              <div key={k} className="min-w-0">
                <dt className="label">{k}</dt>
                <dd className="font-mono text-slate-300 truncate">{v}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div>
          <div className="label mb-2">Dossier contents</div>
          <ol className="space-y-1">
            {SECTIONS.map(([title, sub], i) => (
              <li key={title} className="flex gap-3 bg-panel2 rounded px-3 py-2">
                <span className="font-mono text-[10px] text-violet pt-0.5">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <div className="min-w-0">
                  <div className="text-[11px] text-slate-300">{title}</div>
                  <div className="text-[10px] text-slate-600">{sub}</div>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="primary"
            onClick={run}
            disabled={state.status === 'working'}
          >
            {state.status === 'working' ? 'Generating…' : 'Generate & download dossier'}
          </Button>
          {state.status === 'error' && (
            <span className="text-[11px] text-risk-high font-mono">
              {state.error}
            </span>
          )}
          {state.status === 'done' && (
            <span className="text-[11px] text-risk-low font-mono">
              {state.result.filename} · {state.result.sha256?.slice(0, 16)}…
            </span>
          )}
        </div>

        <p className="text-[10px] text-slate-600 leading-relaxed">
          The generated document records analytical findings and the integrity
          of the evidence handled. It does not establish guilt and does not
          identify an account holder.
        </p>
      </div>
    </div>
  )
}
