import { Badge } from '../ui/badge'
import type { Severity } from '../../types/dashboard'

const styles: Record<Severity, string> = {
  informational: 'border-blue-200 bg-blue-50 text-blue-700',
  low: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  medium: 'border-amber-200 bg-amber-50 text-amber-700',
  high: 'border-orange-200 bg-orange-50 text-orange-700',
  critical: 'border-red-200 bg-red-50 text-red-700',
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge className={styles[severity]}>{severity}</Badge>
}
