/**
 * Last line of defence for the demo.
 *
 * The backend already returns a clean {"detail": ...} for unhandled failures,
 * but a rendering error in React unmounts the whole tree and leaves a WHITE
 * SCREEN. On stage that is indistinguishable from the application having
 * crashed, and there is no way to recover without a reload.
 *
 * This catches it, keeps the workspace chrome on screen, and offers a way
 * back — so the worst case becomes a visible message rather than a blank
 * projector.
 */

import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // Keep the detail in the console for us; never put a stack trace on screen.
    console.error('Render error:', error, info?.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div className="min-h-screen flex flex-col">
        <div className="shrink-0 bg-amber-500/15 border-b border-amber-500/40
                        px-4 py-1 text-[10px] tracking-wide text-amber-300">
          <span className="font-bold">
            ⚠ DEMONSTRATION &amp; SYNTHETIC DATA MODE ACTIVE
          </span>
        </div>

        <div className="flex-1 grid place-items-center p-8">
          <div className="max-w-xl w-full organ p-6 space-y-4">
            <div className="text-[10px] font-bold uppercase tracking-[0.14em]
                            text-risk-critical">
              Interface error
            </div>
            <h1 className="text-xl text-slate-100 font-semibold">
              This panel failed to render.
            </h1>
            <p className="text-[13px] text-slate-400 leading-relaxed">
              No case data was changed and nothing was recorded. The analysis
              engines and the chain-of-custody log are unaffected — this is a
              display fault only.
            </p>
            <code className="block font-mono text-[11px] text-slate-500 break-all
                             bg-panel2 rounded px-3 py-2">
              {String(this.state.error?.message ?? this.state.error)}
            </code>
            <div className="flex gap-3 pt-1">
              <button
                onClick={() => this.setState({ error: null })}
                className="px-3 py-1.5 text-xs font-medium rounded border
                           bg-violet/20 border-violet/60 text-violet-200
                           hover:bg-violet/30"
              >
                Try again
              </button>
              <button
                onClick={() => window.location.reload()}
                className="px-3 py-1.5 text-xs font-medium rounded border
                           bg-panel2 border-edge text-slate-300
                           hover:border-slate-600"
              >
                Reload workspace
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }
}
