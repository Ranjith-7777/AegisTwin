import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { RecentIncident } from '../../hooks/useRangeActivity'
import { formatStamp } from '../../lib/activity'
import { orchestrationState } from '../../lib/orchestrationState'
import type { SimulationScenario } from '../../types/simulation'

const SEVERITY_CLASS: Record<string, string> = {
  critical: 'sev sev-critical',
  high: 'sev sev-high',
  medium: 'sev sev-medium',
  low: 'sev sev-low',
}

/** Response status of an incident, from the orchestration that handled it. */
function incidentStatus(item: RecentIncident): { label: string; tone: string } {
  if (item.orchestration) {
    const state = orchestrationState(item.orchestration.current_state)
    return { label: state.label, tone: state.tone }
  }
  if (item.incident.correlation_state === 'closed') return { label: 'Closed', tone: 'neutral' }
  return { label: 'Open · no response', tone: 'warn' }
}

/** Correlated incidents from the most recent runs, joined to their response. */
export function RecentIncidents({
  items,
  loading,
  scenarios,
  className,
  compact = false,
}: {
  items: RecentIncident[]
  loading: boolean
  scenarios: SimulationScenario[]
  className?: string
  /** Overview mode: fewer rows and only the columns needed to triage. */
  compact?: boolean
}) {
  const scenarioName = (id: string) => scenarios.find((item) => item.scenario_id === id)?.name ?? id
  return (
    <section className={`panel ${className ?? ''}`} aria-label="Recent incidents">
      <header className="panel-head">
        <h2 className="panel-title">Recent incidents</h2>
        <Link className="card-link" to="/incidents">
          View all <ArrowRight className="size-3.5" />
        </Link>
      </header>
      <div className="panel-body is-flush">
        {items.length > 0 ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Scenario</th>
                  <th>Priority</th>
                  {compact ? null : <th>Tactics</th>}
                  <th>Response</th>
                  {compact ? null : <th>Started (UTC)</th>}
                </tr>
              </thead>
              <tbody>
                {items.slice(0, compact ? 5 : 8).map((item) => {
                  const status = incidentStatus(item)
                  const tactics = item.incident.observed_tactic_ids
                  return (
                    <tr key={item.incident.incident_candidate_id}>
                      <td>
                        <span className="incident-id" title={item.incident.incident_candidate_id}>
                          {item.incident.incident_candidate_id.slice(0, 8)}
                        </span>
                      </td>
                      <td
                        className="is-primary"
                        title={`${item.incident.title} · ${String(item.incident.involved_asset_ids.length)} assets involved`}
                      >
                        {scenarioName(item.run.scenario_id)}
                      </td>
                      <td>
                        <span
                          className={SEVERITY_CLASS[item.incident.priority] ?? 'sev sev-neutral'}
                        >
                          {item.incident.priority}
                        </span>
                      </td>
                      {compact ? null : (
                        <td title={tactics.join(', ')}>
                          {tactics[0] ?? '—'}
                          {tactics.length > 1 ? (
                            <span className="text-[var(--text-faint)]"> +{tactics.length - 1}</span>
                          ) : null}
                        </td>
                      )}
                      <td>
                        <span className={`state-pill tone-${status.tone}`}>{status.label}</span>
                      </td>
                      {compact ? null : (
                        <td className="whitespace-nowrap">
                          {formatStamp(item.run.created_at).slice(5)}
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="empty-state">
            {loading
              ? 'Loading incident history…'
              : 'No correlated incidents yet. Incidents appear once a replay is scored and correlated.'}
          </p>
        )}
      </div>
    </section>
  )
}
