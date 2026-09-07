/**
 * In-app PDF viewer.
 *
 * Generated documents used to be handed to a new browser tab. That fails twice
 * over: the tab carries no Authorization header, and the download route sets
 * Content-Disposition: attachment, so even once authenticated the browser
 * SAVES the file and abandons the tab on about:blank - which is what a judge
 * sees a second after pressing the button.
 *
 * Rendering the blob here removes the browser from the decision entirely. The
 * document appears in the application, in context, with the officer still
 * looking at the case. Saving it stays available, but as a choice rather than
 * as a side effect.
 */

import { useEffect } from 'react'

export default function DocumentViewer({ doc, onClose }) {
  // Escape closes. A modal that traps an officer mid-demonstration is worse
  // than no modal.
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!doc) return null

  const save = () => {
    const a = document.createElement('a')
    a.href = doc.blobUrl
    a.download = doc.filename
    a.click()
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center
                 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={doc.filename}
    >
      <div
        className="w-full max-w-5xl h-full max-h-[92vh] flex flex-col rounded
                   border border-edge bg-panel overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="shrink-0 flex items-center gap-3 flex-wrap px-4 py-2.5
                        border-b border-edge">
          <div className="min-w-0">
            <div className="label">Generated document</div>
            <div className="font-mono text-[11px] text-slate-200 truncate">
              {doc.filename}
            </div>
          </div>
          <span className="text-[10px] text-slate-500 font-mono">
            {(doc.bytes / 1024).toFixed(1)} KB
          </span>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={save}
              className="px-2.5 py-1 text-[11px] font-mono rounded border
                         border-edge text-slate-300 hover:text-slate-100
                         hover:border-violet/60"
            >
              SAVE
            </button>
            <button
              onClick={onClose}
              aria-label="Close document"
              className="px-2.5 py-1 text-[13px] leading-none rounded border
                         border-edge text-slate-400 hover:text-slate-100"
            >
              ×
            </button>
          </div>
        </div>

        {/* A browser configured to download PDFs rather than display them will
            leave this frame blank, so the fallback underneath is not
            decorative - it is the only route to the document in that case. */}
        <div className="flex-1 min-h-0 relative bg-panel2">
          <div className="absolute inset-0 grid place-items-center p-6
                          pointer-events-none">
            <p className="text-[11px] text-slate-600 text-center max-w-sm">
              If the document does not appear, this browser is set to download
              PDFs rather than display them. Use SAVE above.
            </p>
          </div>
          <iframe
            src={doc.blobUrl}
            title={doc.filename}
            className="absolute inset-0 w-full h-full border-0"
          />
        </div>
      </div>
    </div>
  )
}
