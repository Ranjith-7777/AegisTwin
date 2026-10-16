import { Swords } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { formatClock } from '../../lib/activity'

/** Live pill describing the Red Agent replay state. */
export function RedAgentStatePill() {
  const playback = useSimulationPlayback()
  const state = playback.activeRun ? playback.playbackState : 'idle'
  if (state === 'playing')
    return (
      <span className="live-pill">
        <span className="status-dot is-live" aria-hidden="true" /> Live
      </span>
    )
  if (state === 'completed')
    return (
      <span className="live-pill is-done">
        <span className="status-dot" aria-hidden="true" /> Replay complete
      </span>
    )
  return (
    <span className="live-pill is-idle">
      <span className="status-dot" aria-hidden="true" /> {state === 'idle' ? 'Idle' : state}
    </span>
  )
}

/**
 * The ATT&CK techniques the correlation engine mapped from the replayed
 * Red Agent telemetry, newest first, stamped with the synthetic event time.
 */
export function RedAgentActivity({ limit = 4, className }: { limit?: number; className?: string }) {
  const playback = useSimulationPlayback()
  const timestamps = new Map(playback.events.map((event) => [event.event_id, event.timestamp]))
  const items = [...playback.techniqueTimeline]
    .sort((left, right) => right.sequence_number - left.sequence_number)
    .slice(0, limit)
  return (
    <section className={`panel ${className ?? ''}`} aria-label="Red Agent activity">
      <header className="panel-head">
        <div>
          <h2 className="panel-title">Recent activity</h2>
          <p className="panel-subtitle">ATT&CK techniques detected in the current replay</p>
        </div>
        <RedAgentStatePill />
      </header>
      <div className="panel-body is-scroll">
        {items.length > 0 ? (
          <ol className="activity-feed">
            {items.map((item) => (
              <li key={item.mapping_id}>
                <span className="activity-time">
                  {formatClock(timestamps.get(item.event_id)).slice(0, 5)}
                </span>
                <span
                  className={
                    item.mapping_confidence >= 0.85 ? 'activity-dot' : 'activity-dot is-warn'
                  }
                  aria-hidden="true"
                />
                <span className="min-w-0">
                  <p className="activity-title">{item.technique_name}</p>
                  <p className="activity-meta">
                    <span>Tactic: {item.tactic}</span>
                    <span>Technique: {item.technique_id}</span>
                  </p>
                </span>
              </li>
            ))}
          </ol>
        ) : (
          <div className="empty-state">
            <Swords className="size-6" />
            <span>
              {playback.activeRun
                ? 'No technique mapped yet - correlation runs as evidence arrives.'
                : 'No attack is running.'}
            </span>
            {!playback.activeRun ? (
              <Link className="card-link" to="/red-agent">
                Launch a scenario
              </Link>
            ) : null}
          </div>
        )}
      </div>
    </section>
  )
}
