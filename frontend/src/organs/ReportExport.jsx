/**
 * ORGAN 7 — Court Dossier Exporter.  Owner: FE2
 *
 * The Report Engine lands in Phase 5. The contract is already frozen, so this
 * organ is wired against the real shape and surfaces the 501 honestly rather
 * than faking a download.
 */

import { useState } from 'react'
import { Button } from '../components/ui'
import { generateReport, generateSTR } from '../api'

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
  const [str, setStr] = useState({ status: 'idle' })

  async function runStr() {
    setStr({ status: 'working' })
    try {
      const r = await generateSTR(kase.case_id)
      setStr({ status: 'done', result: r })
      window.open(r.download_url, '_blank', 'noopener')
    } catch (e) {
      setStr({ status: 'error', error: e.message })
    }
  }

  async function run() {
    setState({ status: 'working' })
    try {
      const r = await generateReport(kase.case_id)
      setState({ status: 'done', result: r })
      // Open in a new tab rather than forcing a save: on stage the officer
      // wants to SHOW the dossier, and a silent download to disk looks like
      // nothing happened.
      window.open(r.download_url, '_blank', 'noopener')
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
        </div>

        {state.status === 'done' && (
          <div className="organ p-3 space-y-2">
            <div className="text-[10px] font-bold uppercase tracking-wider text-risk-low">
              ✓ Dossier generated · {state.result.page_count} pages
            </div>
            <div>
              <div className="label mb-1">
                Detached verification record · SHA-256
              </div>
              <code className="block font-mono text-[10px] text-slate-300 break-all
                               bg-panel2 rounded px-2 py-1.5">
                {state.result.sha256}
              </code>
              <p className="text-[10px] text-slate-600 mt-1 leading-relaxed">
                A document cannot contain its own digest, so this hash is issued
                separately and written to the chain-of-custody log. Verify by
                computing SHA-256 of the downloaded PDF and comparing.
              </p>
            </div>
            <a
              href={state.result.download_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block text-[11px] text-violet hover:underline font-mono"
            >
              {state.result.filename} ↗
            </a>
          </div>
        )}

        <p className="text-[10px] text-slate-600 leading-relaxed">
          The generated document records analytical findings and the integrity
          of the evidence handled. It does not establish guilt and does not
          identify an account holder.
        </p>

        {/* ------------------------------------------- FIU-IND STR draft */}
        <div className="pt-4 mt-2 border-t border-edge space-y-3">
          <div>
            <div className="label mb-1">FIU-IND Suspicious Transaction Report</div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Generates the STR field set as a reviewable draft, with the
              grounds of suspicion carried straight from the deterministic
              indicators.
            </p>
          </div>

          <div className="rounded border border-risk-critical/40
                          bg-risk-critical/10 px-3 py-2">
            <div className="text-[10px] font-bold uppercase tracking-wider
                            text-risk-critical mb-1">
              Draft only — this software cannot file
            </div>
            <p className="text-[10px] text-slate-400 leading-relaxed">
              FIU-IND's FINnet portal has no public submission API, and filing
              requires the submitting organisation to be a registered Reporting
              Entity whose Principal Officer signs the report. The draft must be
              reviewed and lodged by that entity. There is deliberately no
              &ldquo;file&rdquo; action anywhere in this system.
            </p>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <Button onClick={runStr} disabled={str.status === 'working'}>
              {str.status === 'working' ? 'Generating…' : 'Generate draft STR'}
            </Button>
            {str.status === 'error' && (
              <span className="text-[11px] text-risk-high font-mono">
                {str.error}
              </span>
            )}
          </div>

          {str.status === 'done' && (
            <div className="organ p-3 space-y-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-[10px] font-bold px-1.5 py-0.5
                                 rounded bg-risk-critical/20 text-risk-critical">
                  {str.result.status} · NOT FILED
                </span>
                <span className="font-mono text-[10px] text-slate-500">
                  {str.result.str_reference}
                </span>
              </div>
              <p className="text-[10px] text-slate-500 leading-relaxed">
                {str.result.filing_instruction}
              </p>
              <a
                href={str.result.download_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block text-[11px] text-violet hover:underline
                           font-mono"
              >
                {str.result.filename} ↗
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
