/**
 * ORGAN 2 — Evidence Uploader.  Owner: FE1
 *
 * The file is hashed IN THE BROWSER with Web Crypto before it is sent. That
 * hash is the first link in the chain of custody: the server re-hashes on
 * receipt and rejects the upload if the two disagree, so a file that mutated
 * in transit can never enter the evidence table.
 *
 * Parsing and hashing both run entirely client-side, so this organ is fully
 * functional with the backend switched off.
 */

import { useRef, useState } from 'react'
import Papa from 'papaparse'
import { Button, ConfidenceTag, short, timeIST } from '../components/ui'
import { hashFile } from '../api'

const ALLOWED = ['csv', 'pdf', 'txt']

export default function EvidenceUploader({ evidence = [] }) {
  const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [staged, setStaged] = useState(null)
  const inputRef = useRef(null)

  async function ingest(file) {
    setError(null)
    setStaged(null)

    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!ALLOWED.includes(ext)) {
      setError(`Unsupported file type ".${ext}". Accepts CSV, PDF or TXT.`)
      return
    }

    setBusy(true)
    try {
      const sha256 = await hashFile(file)

      let preview = null
      if (ext === 'csv') {
        preview = await new Promise((resolve) => {
          Papa.parse(file, {
            header: true,
            skipEmptyLines: true,
            preview: 5,
            complete: (r) =>
              resolve({ columns: r.meta.fields ?? [], rows: r.data }),
            error: () => resolve(null),
          })
        })
      }

      setStaged({
        name: file.name,
        size: file.size,
        ext,
        sha256,
        preview,
        at: new Date().toISOString(),
      })
    } catch (e) {
      setError(`Could not read the file: ${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="p-4 space-y-4 overflow-y-auto h-full">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDrag(true)
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDrag(false)
          const f = e.dataTransfer.files?.[0]
          if (f) ingest(f)
        }}
        onClick={() => inputRef.current?.click()}
        className={`rounded border-2 border-dashed px-6 py-8 text-center cursor-pointer
          transition-colors ${
            drag
              ? 'border-violet bg-violet/10'
              : 'border-edge hover:border-slate-600'
          }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.pdf,.txt"
          hidden
          onChange={(e) => e.target.files?.[0] && ingest(e.target.files[0])}
        />
        <p className="text-sm text-slate-300">
          {busy ? 'Hashing…' : 'Drag and drop evidence here'}
        </p>
        <p className="text-[10px] text-slate-600 mt-1">
          CSV, PDF or TXT · hashed locally before upload
        </p>
      </div>

      {error && (
        <div className="rounded border border-risk-critical/50 bg-risk-critical/10
                        px-3 py-2 text-[11px] text-risk-critical">
          {error}
        </div>
      )}

      {staged && (
        <div className="organ p-3 space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-200 truncate flex-1">
              {staged.name}
            </span>
            <span className="font-mono text-[10px] text-slate-600">
              {(staged.size / 1024).toFixed(1)} KB
            </span>
          </div>

          <div>
            <div className="label mb-1">SHA-256 · computed in browser</div>
            <code className="block font-mono text-[10px] text-risk-low break-all
                             bg-panel2 rounded px-2 py-1.5">
              {staged.sha256}
            </code>
            <p className="text-[10px] text-slate-600 mt-1">
              The server recomputes this on receipt. A mismatch rejects the
              upload rather than storing unverified evidence.
            </p>
          </div>

          {staged.preview && (
            <div>
              <div className="label mb-1">
                Detected columns · {staged.preview.columns.length}
              </div>
              <div className="overflow-x-auto rounded border border-edge">
                <table className="w-full text-[10px]">
                  <thead>
                    <tr>
                      {staged.preview.columns.map((c) => (
                        <th
                          key={c}
                          className="label px-2 py-1 text-left whitespace-nowrap
                                     border-b border-edge bg-panel2"
                        >
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {staged.preview.rows.map((r, i) => (
                      <tr key={i}>
                        {staged.preview.columns.map((c) => (
                          <td
                            key={c}
                            className="px-2 py-1 font-mono text-slate-500
                                       whitespace-nowrap border-b border-edge/40"
                          >
                            {String(r[c] ?? '')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-[10px] text-slate-600 mt-1">
                Column mapping to the case schema is applied server-side at
                ingestion.
              </p>
            </div>
          )}

          <label className="flex items-center gap-2 text-[11px] text-slate-400">
            <input type="checkbox" defaultChecked className="accent-violet" />
            Mark as synthetic / demonstration data
          </label>
        </div>
      )}

      <div>
        <div className="label mb-2">Ingested evidence · {evidence.length}</div>
        <div className="overflow-x-auto rounded border border-edge">
          <table className="w-full text-[11px]">
            <thead>
              <tr>
                {['File', 'Rows', 'SHA-256', 'Integrity', 'Uploaded'].map((h) => (
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
              {evidence.map((e) => (
                <tr key={e.evidence_id} className="border-b border-edge/40 last:border-0">
                  <td className="px-3 py-2 text-slate-300 whitespace-nowrap">
                    {e.filename}
                  </td>
                  <td className="px-3 py-2 font-mono text-slate-500">
                    {e.row_count ?? '—'}
                  </td>
                  <td className="px-3 py-2 font-mono text-[10px] text-slate-500">
                    {short(e.sha256_server, 12, 6)}
                  </td>
                  <td className="px-3 py-2">
                    <ConfidenceTag value={e.hash_match ? 'confirmed' : 'unknown'} />
                  </td>
                  <td className="px-3 py-2 font-mono text-[10px] text-slate-600
                                 whitespace-nowrap">
                    {timeIST(e.uploaded_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
