import { ArrowRight, ShieldAlert, Swords } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { formatClock } from '../../lib/activity'
import type { TechniqueObservation } from '../../types/correlation'

const TACTIC_COLORS = ['#7c3aed', '#6366f1', '#0891b2', '#16a34a', '#d97706', '#dc2626', '#db2777']

function initials(value: string) {
  return value
    .split(/\s+/)
    .map((word) => word.charAt(0))
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

/** Mapped ATT&CK techniques of the current run, in replay order. */
export function ScenarioTimeline() {
  const playback = useSimulationPlayback()
  const timestamps = new Map(playback.events.map((event) => [event.event_id, event.timestamp]))
  const items = [...playback.techniqueTimeline].sort(
    (left, right) => left.sequence_number - right.sequence_number,
  )
  return (
    <section className="panel" aria-label="Red Agent scenario timeline">
      <header className="panel-head">
        <div>
          <h2 className="panel-title">Red Agent Scenario Timeline</h2>
          <p className="panel-subtitle">Scripted adversary steps, as detected</p>
        </div>
        <Link className="card-link" to="/incidents">
          Full timeline <ArrowRight className="size-3.5" />
        </Link>
      </header>
      <div className="panel-body is-scroll">
        {items.length ? (
          <ol className="tl">
            {items.map((item) => (
              <li key={item.mapping_id}>
                <time>{formatClock(timestamps.get(item.event_id)).slice(0, 5)}</time>
                <span className="min-w-0">
                  <p title={item.technique_name}>{item.technique_name}</p>
                  <small title={item.rationale}>{item.rationale}</small>
                </span>
                <span className="tech-pill">{item.technique_id}</span>
              </li>
            ))}
          </ol>
        ) : (
          <div className="empty-state">
            <Swords className="size-6" />
            <span>
              {playback.activeRun
                ? 'No technique mapped yet.'
                : 'Launch a scenario from the Red Agent lab to build a timeline.'}
            </span>
          </div>
        )}
      </div>
    </section>
  )
}

/** Techniques of the current run grouped by tactic, with mapping confidence. */
export function MitreMapping() {
  const playback = useSimulationPlayback()
  const byTechnique = new Map<string, TechniqueObservation>()
  for (const item of playback.techniqueTimeline) {
    const existing = byTechnique.get(item.technique_id)
    if (!existing || item.mapping_confidence > existing.mapping_confidence)
      byTechnique.set(item.technique_id, item)
  }
  const tactics = [...new Set([...byTechnique.values()].map((item) => item.tactic))]
  const rows = [...byTechnique.values()].sort(
    (left, right) =>
      tactics.indexOf(left.tactic) - tactics.indexOf(right.tactic) ||
      left.sequence_number - right.sequence_number,
  )
  return (
    <section className="panel" aria-label="MITRE ATT&CK mapping">
      <header className="panel-head">
        <div>
          <h2 className="panel-title">MITRE ATT&CK Mapping</h2>
          <p className="panel-subtitle">Curated catalogue · mapping confidence</p>
        </div>
        <Link className="card-link" to="/mitre">
          ATT&CK <ArrowRight className="size-3.5" />
        </Link>
      </header>
      <div className="panel-body is-scroll">
        {rows.length ? (
          <ul className="mitre-list">
            {rows.map((item) => (
              <li key={item.technique_id}>
                <span
                  className="tactic-avatar"
                  style={{
                    background:
                      TACTIC_COLORS[tactics.indexOf(item.tactic) % TACTIC_COLORS.length] ??
                      '#64748b',
                  }}
                  aria-hidden="true"
                >
                  {initials(item.tactic)}
                </span>
                <span className="min-w-0">
                  <p>{item.tactic}</p>
                  <small>
                    {item.technique_id} · {item.technique_name}
                  </small>
                </span>
                <span
                  className={`sev ${item.mapping_confidence >= 0.85 ? 'sev-high' : item.mapping_confidence >= 0.7 ? 'sev-medium' : 'sev-low'}`}
                  title="Mapping confidence from the correlation engine (not attack probability)"
                >
                  {item.mapping_confidence.toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="empty-state">
            <ShieldAlert className="size-6" />
            <span>Techniques appear as correlation maps replayed evidence.</span>
          </div>
        )}
      </div>
    </section>
  )
}
