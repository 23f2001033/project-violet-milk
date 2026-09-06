/**
 * ORGAN 1 — Case Intake.  Owner: FE1
 * Mirrors standard Indian police intake so an IO recognises the form:
 * FIR/NCRP reference, loss in rupees, incident time, and the Sec 94 BNSS
 * production order that authorises the off-chain half of the investigation.
 */

import { useState } from 'react'
import { Button } from '../components/ui'
import { inr, updateCase } from '../api'

function Field({ label, children, hint, wide }) {
  return (
    <label className={`block ${wide ? 'sm:col-span-2' : ''}`}>
      <span className="label block mb-1">{label}</span>
      {children}
      {hint && <span className="block text-[10px] text-slate-600 mt-1">{hint}</span>}
    </label>
  )
}

const input =
  'w-full bg-panel2 border border-edge rounded px-2.5 py-1.5 text-xs ' +
  'font-mono text-slate-200 placeholder:text-slate-700 ' +
  'focus:border-violet focus:outline-none'

export default function CaseIntake({ kase, onSaved }) {
  const [save, setSave] = useState({ status: 'idle' })
  const [form, setForm] = useState({
    fir_ref: kase.fir_ref,
    ncrp_ref: kase.ncrp_ref,
    victim_amount_inr: kase.victim_amount_inr,
    incident_datetime: kase.incident_datetime.slice(0, 16),
    seed_wallet: kase.seed_wallet ?? '',
    seed_utr: kase.seed_utr ?? '',
    io_name: kase.io_name,
    notes: kase.notes,
  })

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function submit() {
    setSave({ status: 'working' })
    try {
      // The API exposes a deliberately narrow update surface: notes, status,
      // seed wallet and data mode. Immutable case facts - the FIR reference,
      // the reported loss, the incident time - are not editable after
      // creation, because silently rewriting them would break the custody
      // trail the dossier depends on.
      await updateCase(kase.case_id, {
        notes: form.notes,
        seed_wallet: form.seed_wallet || null,
      })
      setSave({ status: 'done' })
      onSaved?.()
    } catch (e) {
      setSave({ status: 'error', error: e.message })
    }
  }

  return (
    <div className="p-5 overflow-y-auto h-full">
      <div className="max-w-3xl space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Case ID" hint="Auto-generated on creation">
            <input className={input} value={kase.case_id} readOnly />
          </Field>
          <Field label="Investigating officer">
            <input className={input} value={form.io_name} onChange={set('io_name')} />
          </Field>

          <Field label="FIR reference">
            <input className={input} value={form.fir_ref} onChange={set('fir_ref')} />
          </Field>
          <Field label="NCRP / 1930 reference">
            <input className={input} value={form.ncrp_ref} onChange={set('ncrp_ref')} />
          </Field>

          <Field
            label="Victim loss (INR)"
            hint={inr(Number(form.victim_amount_inr) || 0)}
          >
            <input
              className={input}
              type="number"
              value={form.victim_amount_inr}
              onChange={set('victim_amount_inr')}
            />
          </Field>
          <Field label="Incident date &amp; time">
            <input
              className={input}
              type="datetime-local"
              value={form.incident_datetime}
              onChange={set('incident_datetime')}
            />
          </Field>

          <Field
            label="Known wallet address"
            hint="Trace seed. Leave blank if not yet identified."
            wide
          >
            <input
              className={input}
              value={form.seed_wallet}
              onChange={set('seed_wallet')}
              placeholder="0x…"
            />
          </Field>

          <Field label="Bank UTR">
            <input className={input} value={form.seed_utr} onChange={set('seed_utr')} />
          </Field>
          <Field
            label="Sec 94 BNSS production order"
            hint="Upload via Evidence Ingestion — it is hashed and entered in
                  the custody register like any other document"
          >
            <div className="text-[11px] text-slate-600 bg-panel2 border border-edge
                            rounded px-2.5 py-1.5">
              Handled by the Evidence Ingestion organ
            </div>
          </Field>

          <Field label="Investigator notes" wide>
            <textarea
              className={`${input} h-20 resize-none`}
              value={form.notes}
              onChange={set('notes')}
            />
          </Field>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <Button
            variant="primary"
            onClick={submit}
            disabled={save.status === 'working'}
          >
            {save.status === 'working' ? 'Saving…' : 'Save case'}
          </Button>
          {save.status === 'done' && (
            <span className="text-[11px] text-risk-low font-mono">
              ✓ saved · audit row written
            </span>
          )}
          {save.status === 'error' && (
            <span className="text-[11px] text-risk-critical font-mono">
              {save.error}
            </span>
          )}
          <span className="text-[10px] text-slate-600">
            Demonstration workspace · all identities synthetic
          </span>
        </div>

        <p className="text-[10px] text-slate-600 leading-relaxed max-w-xl">
          Case facts fixed at creation — FIR reference, reported loss and
          incident time — are shown read-only in effect: editing them after
          evidence has been ingested would break the chain of custody the
          dossier relies on. Notes and the trace seed remain editable.
        </p>
      </div>
    </div>
  )
}
