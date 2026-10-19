import { Microscope } from 'lucide-react'
import { useMemo, useState } from 'react'

import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { Badge } from '../ui/badge'
import { Bar, KeyValue, Panel } from '../ui/panel'

/** The hybrid detector's weighted components (backend HYBRID_WEIGHTS). */
const COMPONENTS: { key: string; label: string; weight: number }[] = [
  { key: 'isolation_forest', label: 'Isolation Forest rank', weight: 0.35 },
  { key: 'robust_numerical_deviation', label: 'Numerical deviation', weight: 0.25 },
  { key: 'categorical_rarity', label: 'Categorical rarity', weight: 0.15 },
  { key: 'behavioural_transition_rarity', label: 'Behavioural transition rarity', weight: 0.15 },
  { key: 'infrastructure_novelty', label: 'Infrastructure novelty', weight: 0.1 },
]

/**
 * Explains one persisted anomaly assessment: the calibrated hybrid score
 * against the threshold, the contributing signals, and each weighted
 * component that produced the score. Values are read from the assessment;
 * nothing is recomputed in the browser.
 */
export function AnomalyExplainer() {
  const playback = useSimulationPlayback()
  const ordered = useMemo(
    () =>
      [...playback.assessmentTimeline].sort(
        (left, right) => right.hybrid_anomaly_score - left.hybrid_anomaly_score,
      ),
    [playback.assessmentTimeline],
  )
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const assessment = ordered.find((item) => item.assessment_id === selectedId) ?? ordered[0] ?? null
  const event = assessment
    ? playback.events.find((item) => item.event_id === assessment.event_id)
    : undefined

  return (
    <Panel title="Anomaly explanation" icon={<Microscope className="size-4" />}>
      {!assessment ? (
        <p className="m-0 text-[0.8rem] text-[var(--text-faint)]">
          Run a scenario with detection enabled to explain individual anomaly assessments.
        </p>
      ) : (
        <div className="grid gap-3">
          <label className="field">
            <span>Assessment</span>
            <select
              aria-label="Assessment to explain"
              value={assessment.assessment_id}
              onChange={(change) => {
                setSelectedId(change.target.value)
              }}
            >
              {ordered.map((item) => (
                <option key={item.assessment_id} value={item.assessment_id}>
                  #{item.sequence_number} · {item.hybrid_anomaly_score.toFixed(3)} ·{' '}
                  {item.classification}
                </option>
              ))}
            </select>
          </label>
          <div className="flex items-center gap-2">
            <Badge tone={assessment.classification === 'anomalous' ? 'warn' : 'ok'}>
              {assessment.classification}
            </Badge>
            <span className="text-[0.76rem] text-[var(--text-dim)]">
              {event
                ? `${event.event_type} · ${event.source_id} → ${event.destination_id ?? '—'}`
                : `event #${String(assessment.sequence_number)}`}
            </span>
          </div>
          <div className="grid gap-1">
            <div className="flex justify-between text-[0.72rem] text-[var(--text-faint)]">
              <span>Calibrated hybrid score</span>
              <span className="mono">
                {assessment.hybrid_anomaly_score.toFixed(3)} / threshold{' '}
                {assessment.threshold.toFixed(3)}
              </span>
            </div>
            <div className="relative">
              <Bar
                value={assessment.hybrid_anomaly_score}
                tone={assessment.classification === 'anomalous' ? 'warn' : 'ok'}
                label="Hybrid anomaly score"
              />
              <span
                className="absolute top-[-3px] h-3 w-0.5 bg-[var(--text)]"
                style={{ left: `${String(Math.min(100, assessment.threshold * 100))}%` }}
                aria-hidden="true"
                title="Calibrated threshold"
              />
            </div>
          </div>
          <div className="grid gap-1.5">
            <p className="text-label">Weighted components</p>
            {COMPONENTS.map((component) => {
              const value = assessment.component_scores[component.key] ?? 0
              return (
                <div
                  key={component.key}
                  className="grid grid-cols-[11rem_1fr_3rem] items-center gap-2 text-[0.74rem]"
                >
                  <span className="text-[var(--text-dim)]">
                    {component.label}{' '}
                    <span className="text-[var(--text-faint)]">×{component.weight}</span>
                  </span>
                  <Bar value={value} label={component.label} />
                  <span className="mono text-right">{value.toFixed(2)}</span>
                </div>
              )
            })}
          </div>
          <KeyValue
            left
            rows={[
              ['Contributing signals', assessment.contributing_signals.join(', ') || 'none'],
              ['Detector', `${assessment.detector_type} · ${assessment.calibration_method}`],
            ]}
          />
        </div>
      )}
    </Panel>
  )
}
