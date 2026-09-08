/**
 * ORGAN 7 — Court Dossier Exporter.  Owner: FE2
 *
 * The Report Engine lands in Phase 5. The contract is already frozen, so this
 * organ is wired against the real shape and surfaces the 501 honestly rather
 * than faking a download.
 */

import { useState } from 'react'
import { Button } from '../components/ui'
import {
  generateNotice, generateReferral, generateReport, generateSTR, loadDocument,
} from '../api'
import DocumentViewer from '../components/DocumentViewer'

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
  const [notice, setNotice] = useState({ status: 'idle' })
  const [referral, setReferral] = useState({ status: 'idle' })

  async function runReferral() {
    setReferral({ status: 'working' })
    try {
      const r = await generateReferral(kase.case_id)
      setReferral({ status: 'done', result: r })
      await view(r.download_url)
    } catch (e) {
      setReferral({ status: 'error', error: e.message })
    }
  }
  const [doc, setDoc] = useState(null)

  // One place opens documents, so the blob URL is always revoked and a stray
  // object URL cannot outlive the panel.
  async function view(url) {
    try {
      setDoc(await loadDocument(url))
    } catch (e) {
      setNotice((n) => ({ ...n, error: e.message }))
    }
  }

  function closeDoc() {
    if (doc) URL.revokeObjectURL(doc.blobUrl)
    setDoc(null)
  }

  async function runNotice() {
    setNotice({ status: 'working' })
    try {
      const r = await generateNotice(kase.case_id)
      setNotice({ status: 'done', result: r })
      await view(r.download_url)
    } catch (e) {
      setNotice({ status: 'error', error: e.message })
    }
  }

  async function runStr() {
    setStr({ status: 'working' })
    try {
      const r = await generateSTR(kase.case_id)
      setStr({ status: 'done', result: r })
      await view(r.download_url)
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
      await view(r.download_url)
    } catch (e) {
      setState({ status: 'error', error: e.message })
    }
  }

  return (
    <div className="p-5 overflow-y-auto h-full">
      <DocumentViewer doc={doc} onClose={closeDoc} />
      <div className="max-w-2xl space-y-4">
        <div className="organ p-4">
          <div className="text-center border-b border-edge pb-3 mb-3">
            <div className="text-[11px] tracking-[0.18em] text-slate-300 font-bold">
              CHANDIGARH POLICE HACKATHON
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
            <button
              onClick={() => view(state.result.download_url)}
              className="inline-block text-[11px] text-violet hover:underline font-mono"
            >
              {state.result.filename} ↗
              </button>

            {/* Anchoring is a bonus, never a dependency: when it is off the
                dossier is unaffected and we say so rather than hiding it. */}
            {state.result.anchor && (
              <div className="pt-2 mt-1 border-t border-edge">
                <div className="label mb-1">Blockchain anchor</div>
                {state.result.anchor.anchored ? (
                  <>
                    <div className="text-[11px] text-risk-low">
                      ⛓ Anchored in block{' '}
                      <span className="font-mono">
                        {state.result.anchor.block_number}
                      </span>
                      {state.result.anchor.mode === 'contract'
                        ? ' · contract storage'
                        : ' · transaction calldata'}
                    </div>
                    {state.result.anchor.explorer_url && (
                      <a
                        href={state.result.anchor.explorer_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block font-mono text-[10px] text-violet
                                   hover:underline break-all mt-1"
                      >
                        {state.result.anchor.explorer_url} ↗
                      </a>
                    )}
                  </>
                ) : (
                  <div className="text-[11px] text-slate-500">
                    Not anchored — {state.result.anchor.reason}
                  </div>
                )}
                <p className="text-[10px] text-slate-600 mt-1.5 leading-relaxed">
                  {state.result.anchor.proves}
                </p>
              </div>
            )}
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
              <button
                onClick={() => view(str.result.download_url)}
                className="inline-block text-[11px] text-violet hover:underline
                           font-mono"
              >
                {str.result.filename} ↗
                </button>
            </div>
          )}
        </div>

        {/* --------------------------- Sec 94 BNSS production order draft */}
        <div className="pt-4 mt-2 border-t border-edge space-y-3">
          <div>
            <div className="label mb-1">
              Sec 94 BNSS production order to the exchange
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              A wallet address is not a person. This drafts the written order
              that compels the exchange holding the KYC record to produce it —
              with the deposit address, amounts, timestamps and transaction
              hashes recited straight from the trace.
            </p>
          </div>

          <div className="rounded border border-risk-high/40
                          bg-risk-high/10 px-3 py-2">
            <div className="text-[10px] font-bold uppercase tracking-wider
                            text-risk-high mb-1">
              Unsigned draft — no legal effect
            </div>
            <p className="text-[10px] text-slate-400 leading-relaxed">
              Authority to issue comes from the officer&rsquo;s signature, not
              from software. The statutory wording has not been settled by a
              legal practitioner, and the addressee&rsquo;s legal name must be
              established independently before service. Nothing here issues or
              serves anything.
            </p>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <Button onClick={runNotice} disabled={notice.status === 'working'}>
              {notice.status === 'working'
                ? 'Drafting…'
                : 'Draft production order'}
            </Button>
            {notice.status === 'error' && (
              <span className="text-[11px] text-risk-high font-mono">
                {notice.error}
              </span>
            )}
          </div>

          {notice.status === 'done' && (
            <div className="organ p-3 space-y-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-[10px] font-bold px-1.5 py-0.5
                                 rounded bg-risk-high/20 text-risk-high">
                  {notice.result.status} · UNSIGNED
                </span>
                <span className="font-mono text-[10px] text-slate-500">
                  {notice.result.notice_reference}
                </span>
              </div>
              {notice.result.addressee_identified ? (
                <p className="text-[10px] text-slate-400 font-mono break-all">
                  Addressee:{' '}
                  {notice.result.fields.addressee_observed_label}
                  {' · '}
                  {notice.result.fields.addressee_address_on_chain}
                </p>
              ) : (
                <p className="text-[10px] text-risk-high leading-relaxed">
                  This trace reached no exchange, so no addressee could be
                  identified. The draft says so rather than naming anyone.
                </p>
              )}
              <p className="text-[10px] text-slate-500 leading-relaxed">
                {notice.result.issue_instruction}
              </p>
              <button
                onClick={() => view(notice.result.download_url)}
                className="inline-block text-[11px] text-violet hover:underline
                           font-mono"
              >
                {notice.result.filename} ↗
                </button>
            </div>
          )}
        </div>

        {/* ---------------------------- internal referral for dead ends */}
        <div className="pt-4 mt-2 border-t border-edge space-y-3">
          <div>
            <div className="label mb-1">
              Internal referral · addresses that cannot be served
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              A production order compels a <em>person</em> to produce records.
              Where funds rest in an unhosted address, or pass through a mixer
              or bridge, there is no custodian and no operator — an order would
              ask nobody for nothing. This records those addresses for FIU-IND
              lead referral, attribution and monitoring instead.
            </p>
          </div>

          <div className="rounded border border-edge bg-panel2 px-3 py-2">
            <div className="text-[10px] font-bold uppercase tracking-wider
                            text-slate-400 mb-1">
              Internal working note — not a statutory instrument
            </div>
            <p className="text-[10px] text-slate-500 leading-relaxed">
              No provision prescribes this form. It recites no authority,
              compels nobody, and is transmitted to nobody — a referral is made
              by an officer through their own chain.
            </p>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <Button onClick={runReferral} disabled={referral.status === 'working'}>
              {referral.status === 'working'
                ? 'Preparing…'
                : 'Prepare referral note'}
            </Button>
            {referral.status === 'error' && (
              <span className="text-[11px] text-risk-high font-mono">
                {referral.error}
              </span>
            )}
          </div>

          {referral.status === 'done' && (
            <div className="organ p-3 space-y-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-[10px] font-bold px-1.5 py-0.5
                                 rounded bg-panel2 text-slate-400">
                  INTERNAL · NOT TRANSMITTED
                </span>
                <span className="font-mono text-[10px] text-slate-500">
                  {referral.result.referral_reference}
                </span>
              </div>
              <p className="text-[10px] text-slate-400">
                {referral.result.addresses_referred} address
                {referral.result.addresses_referred === 1 ? '' : 'es'} that a
                production order cannot reach.
              </p>
              <p className="text-[10px] text-slate-500 leading-relaxed">
                {referral.result.instruction}
              </p>
              <button
                onClick={() => view(referral.result.download_url)}
                className="inline-block text-[11px] text-violet hover:underline
                           font-mono"
              >
                {referral.result.filename} ↗
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
