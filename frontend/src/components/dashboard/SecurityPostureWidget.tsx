import type { CommandCentreState } from '../../lib/commandCentre'

/**
 * Right-rail donut summarising the same risk/asset evidence already
 * computed for the rest of Command Centre — no separate fabricated metric.
 * The ring shows resilience (100 - riskScore); the rows below break the
 * known synthetic asset population into healthy vs. at-risk counts plus
 * the live incident count.
 */
export function SecurityPostureWidget({
  state,
  totalAssets,
}: {
  state: CommandCentreState
  totalAssets: number
}) {
  const resilience = Math.max(0, 100 - state.riskScore)
  const atRisk = state.degradedNodeIds.length
  const healthy = Math.max(0, totalAssets - atRisk)
  const radius = 30
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - resilience / 100)
  const tone = resilience >= 70 ? 'var(--state-ok)' : resilience >= 40 ? 'var(--state-degraded)' : 'var(--state-attack)'

  return (
    <section className="posture-widget" aria-label="Security posture">
      <div className="posture-ring">
        <svg viewBox="0 0 72 72">
          <circle cx="36" cy="36" r={radius} fill="none" stroke="var(--border)" strokeWidth="8" />
          <circle
            cx="36"
            cy="36"
            r={radius}
            fill="none"
            stroke={tone}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
          />
        </svg>
        <span className="posture-ring-value">{resilience}%</span>
      </div>
      <div className="posture-stats">
        <p className="command-panel-label">Security Posture</p>
        <div className="posture-stat-row">
          <span className="posture-stat-label">
            <span className="chip-dot" style={{ background: 'var(--state-ok)' }} aria-hidden="true" />
            Healthy assets
          </span>
          <span className="posture-stat-value">{healthy}</span>
        </div>
        <div className="posture-stat-row">
          <span className="posture-stat-label">
            <span
              className="chip-dot"
              style={{ background: 'var(--state-degraded)' }}
              aria-hidden="true"
            />
            At risk
          </span>
          <span className="posture-stat-value">{atRisk}</span>
        </div>
        <div className="posture-stat-row">
          <span className="posture-stat-label">
            <span className="chip-dot" style={{ background: 'var(--state-attack)' }} aria-hidden="true" />
            Active incidents
          </span>
          <span className="posture-stat-value">{state.activeIncidents}</span>
        </div>
      </div>
    </section>
  )
}
