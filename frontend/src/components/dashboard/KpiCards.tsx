import { Activity, CloudCog, Gauge, ShieldAlert, type LucideIcon } from 'lucide-react'

import type { CloudHealth, CommandCentreState } from '../../lib/commandCentre'

type Tone = 'healthy' | 'warn' | 'danger' | 'info'

const healthTone: Record<CloudHealth, Tone> = {
  healthy: 'healthy',
  degraded: 'warn',
  'under attack': 'danger',
  mitigated: 'healthy',
}

function riskTone(score: number): Tone {
  if (score >= 60) return 'danger'
  if (score >= 30) return 'warn'
  return 'healthy'
}

export function KpiCards({ state }: { state: CommandCentreState }) {
  const cards: Array<{
    label: string
    value: string
    detail: string
    icon: LucideIcon
    tone: Tone
  }> = [
    {
      label: 'Cloud Health',
      value: state.cloudHealth,
      detail: state.degradedNodeIds.length
        ? `${String(state.degradedNodeIds.length)} degraded assets`
        : 'All assets nominal',
      icon: CloudCog,
      tone: healthTone[state.cloudHealth],
    },
    {
      label: 'Risk Score',
      value: String(state.riskScore),
      detail: 'Weighted anomaly, correlation and prediction',
      icon: Gauge,
      tone: riskTone(state.riskScore),
    },
    {
      label: 'Availability',
      value: `${state.availabilityPercent.toFixed(1)}%`,
      detail: `${String(state.impairedRelationships)}/${String(state.servingRelationships)} serving routes impaired`,
      icon: Activity,
      tone: state.availabilityPercent >= 99 ? 'healthy' : 'warn',
    },
    {
      label: 'Active Incidents',
      value: String(state.activeIncidents),
      detail: state.attackEdgeIds.length
        ? `${String(state.attackEdgeIds.length)} attack routes`
        : 'No correlated incident',
      icon: ShieldAlert,
      tone: state.activeIncidents ? 'danger' : 'healthy',
    },
  ]
  return (
    <section className="kpi-row" aria-label="Cloud posture">
      {cards.map((card) => (
        <article
          key={card.label}
          className={`card kpi-card tone-${card.tone}`}
          aria-label={card.label}
        >
          <div className="kpi-head">
            <span>{card.label}</span>
            <card.icon className="size-4" aria-hidden="true" />
          </div>
          <p className="kpi-value">{card.value}</p>
          <p className="kpi-detail">{card.detail}</p>
        </article>
      ))}
    </section>
  )
}
