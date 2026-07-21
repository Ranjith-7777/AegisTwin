import { Badge } from '../ui/badge'
import type { Severity } from '../../types/dashboard'

const styles: Record<Severity, string> = {
  informational: 'border-cyan-800 bg-cyan-950/60 text-cyan-300',
  low: 'border-emerald-800 bg-emerald-950/60 text-emerald-300',
  medium: 'border-amber-800 bg-amber-950/60 text-amber-300',
  high: 'border-orange-800 bg-orange-950/60 text-orange-300',
  critical: 'border-red-800 bg-red-950/60 text-red-300',
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge className={styles[severity]}>{severity}</Badge>
}
