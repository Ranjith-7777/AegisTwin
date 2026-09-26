import { Bot, ShieldAlert, Swords, TrendingUp, type LucideIcon } from 'lucide-react'

import type { CommandCentreState } from '../../lib/commandCentre'

type Tone = 'indigo' | 'amber' | 'emerald' | 'rose'

/**
 * The four Command Centre headline metrics: Resilience, Threats, Blue Agent
 * and Red Agent — four independent cards, each with a small colored icon
 * badge. Resilience is derived from the same weighted risk score already
 * computed for the rest of the app (100 - riskScore) rather than a
 * separate fabricated figure.
 */
export function CommandKpiRow({ state }: { state: CommandCentreState }) {
  const resilience = Math.max(0, 100 - state.riskScore)
  const cards: Array<{
    label: string
    value: string
    detail: string
    icon: LucideIcon
    tone: Tone
  }> = [
    {
      label: 'Resilience',
      value: `${String(resilience)}%`,
      detail: state.riskBasis,
      icon: TrendingUp,
      tone: 'indigo',
    },
    {
      label: 'Threats',
      value: state.activeIncidents ? `${String(state.activeIncidents)} Active` : 'None',
      detail: state.attackEdgeIds.length
        ? `${String(state.attackEdgeIds.length)} attack routes`
        : 'No correlated incident',
      icon: ShieldAlert,
      tone: state.activeIncidents ? 'rose' : 'emerald',
    },
    {
      label: 'Blue Agent',
      value: state.blueAgentState === 'active' ? 'Active' : 'Ready',
      detail: state.blueAgentDetail,
      icon: Bot,
      tone: 'emerald',
    },
    {
      label: 'Red Agent',
      value: state.redAgentState === 'active' ? 'Active' : 'Idle',
      detail: state.redAgentDetail,
      icon: Swords,
      tone: state.redAgentState === 'active' ? 'rose' : 'amber',
    },
  ]
  return (
    <section className="kpi-grid" aria-label="Command Centre summary">
      {cards.map((card) => (
        <article key={card.label} className="kpi-card" aria-label={card.label}>
          <span className={`kpi-badge tone-${card.tone}`}>
            <card.icon aria-hidden="true" />
          </span>
          <div className="kpi-card-body">
            <p className="kpi-card-label">{card.label}</p>
            <p className="kpi-card-value">{card.value}</p>
            <p className="kpi-card-detail">{card.detail}</p>
          </div>
        </article>
      ))}
    </section>
  )
}
