import { Radio, WifiOff } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { EmptyState } from '../common/EmptyState'
import { SeverityBadge } from '../common/SeverityBadge'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent, CardHeader } from '../ui/card'

export function LiveEventStream({ expanded = false }: { expanded?: boolean }) {
  const {
    events,
    activeRun,
    connectionState,
    error,
    retry,
    detectionEnabled,
    assessmentsByEventId,
    playbackState,
  } = useSimulationPlayback()
  const [autoScroll, setAutoScroll] = useState(true)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (autoScroll && typeof endRef.current?.scrollIntoView === 'function') {
      endRef.current.scrollIntoView({ block: 'nearest' })
    }
  }, [autoScroll, events])

  return (
    <Card className={expanded ? 'xl:col-span-2' : ''}>
      <CardHeader>
        <div>
          <p className="eyebrow">Persisted simulator playback</p>
          <h2 className="panel-title">Live Synthetic Event Stream</h2>
        </div>
        <Radio className="size-5 text-cyan-400" aria-hidden="true" />
      </CardHeader>
      <CardContent>
        <div className="mb-3 flex items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-xs text-slate-400">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(event) => {
                setAutoScroll(event.target.checked)
              }}
            />
            Auto-scroll
          </label>
          <span className="text-xs text-slate-500">Maximum 200 rendered events</span>
        </div>
        {error && activeRun ? (
          <div
            className="mb-3 flex items-center justify-between rounded-lg border border-red-900/60 bg-red-950/20 p-3"
            role="alert"
          >
            <span className="text-sm text-red-200">Playback connection error.</span>
            <Button size="sm" variant="outline" onClick={retry}>
              Retry
            </Button>
          </div>
        ) : null}
        {!activeRun ? (
          <EmptyState
            title="No synthetic run selected"
            detail="Start a deterministic simulation or reopen a previous run to stream its persisted events."
          />
        ) : null}
        {activeRun && connectionState === 'disconnected' && events.length === 0 && !error ? (
          <div
            className="flex items-center gap-2 rounded-lg border border-slate-700 p-4 text-sm text-slate-400"
            role="status"
          >
            <WifiOff className="size-4" />
            Playback is disconnected.
          </div>
        ) : null}
        {events.length > 0 ? (
          <div
            className={expanded ? 'event-stream-list max-h-[38rem]' : 'event-stream-list max-h-96'}
            aria-live="polite"
          >
            {events.map((event, index) =>
              (() => {
                const assessment = assessmentsByEventId[event.event_id]
                return (
                  <article
                    className={index === events.length - 1 ? 'event-item is-current' : 'event-item'}
                    key={event.event_id}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="technical text-xs text-slate-400">
                        {new Date(event.timestamp).toISOString()}
                      </span>
                      <div className="flex items-center gap-2">
                        <Badge className="border-cyan-800 bg-cyan-950/60 text-cyan-300">
                          Synthetic
                        </Badge>
                        <SeverityBadge severity={event.severity} />
                      </div>
                    </div>
                    <div className="mt-2 grid gap-1 text-sm text-slate-300 sm:grid-cols-3">
                      <p>
                        <span className="text-slate-500">Type:</span> {event.event_type}
                      </p>
                      <p>
                        <span className="text-slate-500">Action:</span> {event.action}
                      </p>
                      <p>
                        <span className="text-slate-500">Outcome:</span> {event.outcome}
                      </p>
                    </div>
                    <p className="technical mt-2 text-xs text-slate-400">
                      {event.source_id} → {event.destination_id ?? 'none'}
                      {event.user_id ? ` · ${event.user_id}` : ''}
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      Suspicious-looking exercise data is not a confirmed attack.
                    </p>
                    {detectionEnabled ? (
                      <p className="mt-2 text-xs text-slate-300">
                        <strong>Assessment: </strong>
                        {assessment
                          ? assessment.classification
                          : playbackState === 'completed'
                            ? 'Assessment unavailable'
                            : 'Pending assessment'}
                        {assessment
                          ? ` · score ${assessment.hybrid_anomaly_score.toFixed(3)} · threshold ${assessment.threshold.toFixed(3)} · ${assessment.contributing_signals.length.toString()} signals`
                          : ''}
                      </p>
                    ) : null}
                  </article>
                )
              })(),
            )}
            <div ref={endRef} />
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
