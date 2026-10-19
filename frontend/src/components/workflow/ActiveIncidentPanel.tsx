import { Radar, ShieldAlert } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { meaningfulPrediction } from '../../lib/prediction'
import { Badge, type BadgeTone } from '../ui/badge'
import { Bar, Panel } from '../ui/panel'

const PRIORITY_TONE: Record<string, BadgeTone> = {
  critical: 'danger',
  high: 'danger',
  medium: 'warn',
  low: 'accent',
}

/** The correlated incident for the active run, with its predicted next stage. */
export function ActiveIncidentPanel({ className }: { className?: string }) {
  const playback = useSimulationPlayback()
  const incident = playback.currentIncidentCandidate
  const prediction = meaningfulPrediction(playback.predictionTimeline)
  const top = prediction?.hypotheses[0] ?? null
  return (
    <Panel
      aria-label="Active incident"
      className={className}
      title="Active incident"
      icon={<ShieldAlert className="size-4" />}
      scroll
      actions={
        incident ? (
          <Link className="card-link" to="/incidents">
            Details
          </Link>
        ) : null
      }
    >
      {!incident ? (
        <p className="m-0 text-[0.8rem] text-[var(--text-faint)]">
          {playback.activeRun
            ? playback.correlationEnabled
              ? 'No incident correlated yet - evidence is still arriving.'
              : 'Correlation is disabled for this run.'
            : 'No active incident. Correlated evidence appears here during a scenario.'}
        </p>
      ) : (
        <div className="grid gap-2.5">
          <div className="flex items-start justify-between gap-2">
            <p className="m-0 text-[0.86rem] font-semibold text-[var(--text)]">{incident.title}</p>
            <Badge tone={PRIORITY_TONE[incident.priority] ?? 'neutral'} className="capitalize">
              {incident.priority}
            </Badge>
          </div>
          <div className="grid gap-1">
            <div className="flex justify-between text-[0.72rem] text-[var(--text-faint)]">
              <span>Correlation confidence</span>
              <span className="mono text-[var(--text-dim)]">
                {incident.correlation_score.toFixed(2)}
              </span>
            </div>
            <Bar
              value={incident.correlation_score}
              tone={incident.correlation_score >= 0.7 ? 'danger' : 'warn'}
              label="Correlation confidence"
            />
          </div>
          <div>
            <p className="eyebrow mb-1">MITRE ATT&CK</p>
            <div className="flex flex-wrap gap-1">
              {incident.observed_technique_ids.length > 0 ? (
                incident.observed_technique_ids.map((id) => (
                  <Badge key={id} tone="danger" className="badge-square mono">
                    {id}
                  </Badge>
                ))
              ) : (
                <span className="text-[0.75rem] text-[var(--text-faint)]">None mapped yet</span>
              )}
            </div>
          </div>
          <div>
            <p className="eyebrow mb-1">Affected assets · {incident.involved_asset_ids.length}</p>
            <p className="m-0 text-[0.75rem] leading-relaxed text-[var(--text-dim)]">
              {incident.involved_asset_ids.join(', ') || 'none'}
            </p>
          </div>
          <div className="inset">
            <p className="eyebrow mb-1 flex items-center gap-1">
              <Radar className="size-3" /> Predicted next stage
            </p>
            {top ? (
              <p className="m-0 text-[0.78rem] text-[var(--text)]">
                <span className="mono text-[var(--predicted-text)]">
                  {top.predicted_technique_id ?? top.hypothesis_type}
                </span>{' '}
                {top.predicted_technique_name ?? ''}
                {top.predicted_asset_id ? ` → ${top.predicted_asset_id}` : ''}{' '}
                <span className="text-[var(--text-faint)]">
                  (score {top.prediction_score.toFixed(2)})
                </span>
              </p>
            ) : (
              <p className="m-0 text-[0.75rem] text-[var(--text-faint)]">
                {prediction?.insufficient_evidence_reason ?? 'No hypothesis yet.'}
              </p>
            )}
          </div>
        </div>
      )}
    </Panel>
  )
}
