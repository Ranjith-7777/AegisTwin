import { Pause, Play } from 'lucide-react'
import type { ReactNode } from 'react'

import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { formatClock } from '../../lib/activity'

const STATE_LABEL: Record<string, string> = {
  playing: 'Live replay',
  paused: 'Paused',
  completed: 'Replay complete',
  stopped: 'Stopped',
  error: 'Replay error',
  idle: 'No replay',
}

/**
 * The Red Agent replay as a timeline: pause/resume, the synthetic clock, a
 * track with one marker per replayed event (amber = anomalous, red = ATT&CK
 * technique mapped) and the replay position. Markers come from the live
 * topology history - nothing is plotted ahead of the replay.
 */
export function PlaybackTimeline({ statusLine }: { statusLine: ReactNode }) {
  const playback = useSimulationPlayback()
  const run = playback.activeRun
  const total = Math.max(1, playback.totalEventCount || run?.event_count || 1)
  const history = playback.liveTopology.history
  const lastStamp = history.at(-1)?.timestamp ?? null
  const state = run ? playback.playbackState : 'idle'
  const canToggle = run !== null && (state === 'playing' || state === 'paused')
  return (
    <div className="twin-playback" aria-label="Replay timeline">
      <button
        type="button"
        className="play-button"
        disabled={!canToggle}
        onClick={state === 'playing' ? playback.pause : playback.resume}
        aria-label={state === 'playing' ? 'Pause replay' : 'Resume replay'}
        title={canToggle ? undefined : 'Available while a replay is running'}
      >
        {state === 'playing' ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}
      </button>
      <div className="playback-clock">
        <strong>{lastStamp ? formatClock(lastStamp) : '--:--:--'}</strong>
        <span>
          {state === 'playing' ? (
            <span className="status-dot is-live text-[var(--ok)]" aria-hidden="true" />
          ) : null}
          {STATE_LABEL[state] ?? state}
        </span>
      </div>
      <div className="min-w-0">
        <div className="timeline-track">
          <div className="timeline-rail">
            <span
              style={{
                width: `${String(Math.min(100, (playback.currentEventIndex / total) * 100))}%`,
              }}
            />
          </div>
          {history.map((item) => (
            <span
              key={item.event_id}
              className={`timeline-marker${item.technique_ids.length ? ' is-technique' : item.anomaly_classification === 'anomalous' ? ' is-anomalous' : ''}`}
              style={{ left: `${String((item.sequence_number / total) * 100)}%` }}
              title={`#${String(item.sequence_number)} · ${formatClock(item.timestamp)} · ${item.action}${item.technique_ids.length ? ` · ${item.technique_ids.join(', ')}` : ''}`}
            />
          ))}
        </div>
        <div className="timeline-ticks">
          <span>{run ? formatClock(run.start_time) : '—'}</span>
          {statusLine}
          <span>{lastStamp ? formatClock(lastStamp) : '—'}</span>
        </div>
      </div>
      <span className="chip chip-muted" title="Replay speed multiplier set at launch">
        {run ? `${String(run.playback_speed)}×` : '—'}
      </span>
    </div>
  )
}
