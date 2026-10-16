import { Badge, type BadgeTone } from '../ui/badge'
import type { Severity } from '../../types/dashboard'

const tones: Record<Severity, BadgeTone> = {
  informational: 'accent',
  low: 'ok',
  medium: 'warn',
  high: 'danger',
  critical: 'danger',
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <Badge tone={tones[severity]} className="capitalize">
      {severity}
    </Badge>
  )
}
