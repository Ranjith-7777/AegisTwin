import { CircleDashed, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

export function EmptyState({
  title,
  detail,
  icon: Icon = CircleDashed,
  action,
}: {
  title: string
  detail: ReactNode
  icon?: LucideIcon
  action?: ReactNode
}) {
  return (
    <div className="empty-state">
      <Icon className="size-6" aria-hidden="true" />
      <strong>{title}</strong>
      <p className="m-0 max-w-md">{detail}</p>
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  )
}
