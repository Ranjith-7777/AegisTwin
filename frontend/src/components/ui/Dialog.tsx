import { X } from 'lucide-react'
import { useEffect, useId, useRef, type ReactNode } from 'react'

import { Button } from './button'

/**
 * Accessible modal: focus moves into the dialog, Escape closes it, focus is
 * restored to the opener, and the backdrop click dismisses it.
 */
export function Dialog({
  open,
  title,
  children,
  footer,
  onClose,
}: {
  open: boolean
  title: ReactNode
  children: ReactNode
  footer?: ReactNode
  onClose: () => void
}) {
  const titleId = useId()
  const panel = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const opener = document.activeElement as HTMLElement | null
    const first = panel.current?.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    )
    first?.focus()
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      opener?.focus()
    }
  }, [onClose, open])
  if (!open) return null
  return (
    <div
      className="dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div ref={panel} className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="dialog-head">
          <h2 id={titleId} className="h-section">
            {title}
          </h2>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close dialog">
            <X />
          </Button>
        </div>
        <div className="dialog-body">{children}</div>
        {footer ? <div className="dialog-foot">{footer}</div> : null}
      </div>
    </div>
  )
}
