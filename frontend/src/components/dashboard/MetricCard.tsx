import { Activity, Clock3, Gauge, RadioTower, ShieldAlert } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { Card, CardContent } from '../ui/card'
import type { DashboardMetric } from '../../types/dashboard'

const icons: Record<string, LucideIcon> = {
  'Active Incidents': ShieldAlert,
  'Global Risk Score': Gauge,
  MTTD: Clock3,
  MTTR: Activity,
  'Agents Online': RadioTower,
}

export function MetricCard({ metric }: { metric: DashboardMetric }) {
  const Icon = icons[metric.label] ?? Activity
  return (
    <Card aria-label={metric.label}>
      <CardContent className="flex min-h-32 flex-col justify-between">
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-400">{metric.label}</p>
          <Icon className="size-4 text-cyan-400" aria-hidden="true" />
        </div>
        <div>
          <p className="mt-4 text-3xl font-semibold tracking-tight text-white">{metric.value}</p>
          <p
            className={
              metric.status === 'live'
                ? 'mt-1 text-xs text-cyan-300'
                : 'mt-1 text-xs text-amber-300'
            }
          >
            {metric.detail}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
