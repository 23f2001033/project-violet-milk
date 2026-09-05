/**
 * ORGAN 1 — Case Intake.  Owner: FE1
 * Mirrors standard Indian police intake so an IO recognises the form:
 * FIR/NCRP reference, loss in rupees, incident time, and the Sec 94 BNSS
 * production order that authorises the off-chain half of the investigation.
 */

import { useState } from 'react'
import { Button } from '../components/ui'
import { inr } from '../api'

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

export default function CaseIntake({ kase }) {
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
            hint="Required before off-chain bank or KYC records may be requested"
          >
            <input className={input} type="file" />
          </Field>

          <Field label="Investigator notes" wide>
            <textarea
              className={`${input} h-20 resize-none`}
              value={form.notes}
              onChange={set('notes')}
            />
          </Field>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="primary">Save case</Button>
          <span className="text-[10px] text-slate-600">
            Demonstration workspace · all identities synthetic
          </span>
        </div>
      </div>
    </div>
  )
}
