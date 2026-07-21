import type { LucideIcon } from 'lucide-react'

import { EmptyState } from '../components/common/EmptyState'
import { Card, CardContent } from '../components/ui/card'

export function PlaceholderPage({
  title,
  phase,
  description,
  icon: Icon,
}: {
  title: string
  phase: string
  description: string
  icon: LucideIcon
}) {
  return (
    <div className="space-y-6">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Planned capability · {phase}</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <Icon className="size-7 text-cyan-400" />
      </header>
      <Card>
        <CardContent>
          <EmptyState
            title={`${title} is intentionally deferred`}
            detail={`This route is ready for integration in ${phase}. No unsupported live capability is represented in the current foundation.`}
          />
        </CardContent>
      </Card>
    </div>
  )
}
