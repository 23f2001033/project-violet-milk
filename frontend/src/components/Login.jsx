/**
 * Sign-in.
 *
 * Case data is gated because the chain of custody is only meaningful if the
 * identity in it is verified. Before authentication existed, the officer name
 * was a form field the client filled in.
 */

import { useState } from 'react'
import { login } from '../api'

export default function Login({ onSignedIn }) {
  const [userId, setUserId] = useState('IO_SHARMA')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onSignedIn(await login(userId.trim(), password))
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  const field =
    'w-full bg-panel2 border border-edge rounded px-3 py-2 text-sm ' +
    'font-mono text-slate-200 placeholder:text-slate-700 ' +
    'focus:border-violet focus:outline-none'

  return (
    <div className="min-h-screen flex flex-col">
      <div className="shrink-0 bg-amber-500/15 border-b border-amber-500/40
                      px-4 py-1 text-[10px] tracking-wide text-amber-300">
        <span className="font-bold">
          ⚠ DEMONSTRATION &amp; SYNTHETIC DATA MODE ACTIVE
        </span>
      </div>

      <div className="flex-1 grid place-items-center p-8">
        <form onSubmit={submit} className="w-full max-w-sm space-y-5">
          <div>
            <div className="text-[10px] tracking-[0.15em] text-slate-500">
              CHANDIGARH POLICE HACKATHON
            </div>
            <div className="text-violet font-bold text-lg tracking-tight">
              PROJECT VIOLET MILK
            </div>
          </div>

          <div className="organ p-5 space-y-4">
            <div>
              <label className="label block mb-1.5" htmlFor="uid">
                Officer ID
              </label>
              <input
                id="uid" className={field} value={userId} autoComplete="username"
                onChange={(e) => setUserId(e.target.value)} spellCheck={false}
              />
            </div>
            <div>
              <label className="label block mb-1.5" htmlFor="pw">
                Password
              </label>
              <input
                id="pw" className={field} type="password" value={password}
                autoComplete="current-password" autoFocus
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {error && (
              <div className="text-[11px] text-risk-critical">{error}</div>
            )}

            <button
              type="submit" disabled={busy || !password}
              className="w-full px-3 py-2 text-sm font-medium rounded border
                         bg-violet/20 border-violet/60 text-violet-200
                         hover:bg-violet/30 disabled:opacity-40
                         disabled:cursor-not-allowed"
            >
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </div>

          <p className="text-[10px] text-slate-600 leading-relaxed">
            Every action on a case is recorded against the signed-in officer in
            a hash-chained custody log. Sessions end when the browser closes.
          </p>
        </form>
      </div>
    </div>
  )
}
