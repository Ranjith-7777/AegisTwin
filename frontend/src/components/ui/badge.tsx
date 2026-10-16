import type { HTMLAttributes } from 'react'

import { cn } from '../../lib/utils'

export type BadgeTone =
  'neutral' | 'accent' | 'ok' | 'warn' | 'danger' | 'predicted' | 'proposed' | 'executed'

export function Badge({
  className,
  tone = 'neutral',
  dot = false,
  children,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone; dot?: boolean }) {
  return (
    <span className={cn('badge', `badge-${tone}`, className)} {...props}>
      {dot ? <span className="status-dot" aria-hidden="true" /> : null}
      {children}
    </span>
  )
}
