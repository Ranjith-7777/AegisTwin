import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { Badge } from '../ui/badge'
import { Card, CardContent, CardHeader } from '../ui/card'

const componentLabels: Record<string, string> = {
  isolation_forest: 'Isolation Forest rank',
  robust_numerical_deviation: 'Numerical/context deviation',
  categorical_rarity: 'Categorical rarity',
  behavioural_transition_rarity: 'Transition rarity',
  infrastructure_novelty: 'Infrastructure novelty',
}

export function LiveAnomalyDashboard() {
  const {
    currentAssessment,
    assessmentTimeline,
    events,
    selectedModel,
    playbackState,
    simulatedElapsedSeconds,
  } = useSimulationPlayback()
  const anomalous = assessmentTimeline.filter((item) => item.classification === 'anomalous')
  const normal = assessmentTimeline.length - anomalous.length
  const first = anomalous[0]
  const currentEvent = currentAssessment
    ? events.find((event) => event.event_id === currentAssessment.event_id)
    : null
  const maximum = assessmentTimeline.reduce(
    (value, item) => Math.max(value, item.hybrid_anomaly_score),
    0,
  )
  return (
    <>
      <Card>
        <CardHeader>
          <div>
            <p className="eyebrow">Live synthetic assessment</p>
            <h2 className="panel-title">Current Assessment</h2>
          </div>
          <Badge>Synthetic</Badge>
        </CardHeader>
        <CardContent aria-live="polite">
          {currentAssessment ? (
            <div className="space-y-3 text-sm text-slate-600">
              <p>
                <strong
                  className={
                    currentAssessment.classification === 'anomalous'
                      ? 'text-amber-700'
                      : 'text-emerald-700'
                  }
                >
                  {currentAssessment.classification}
                </strong>{' '}
                · sequence {currentAssessment.sequence_number} · {currentEvent?.action ?? 'event'}
              </p>
              <p>
                Hybrid anomaly score{' '}
                <strong>{currentAssessment.hybrid_anomaly_score.toFixed(3)}</strong> / threshold{' '}
                {currentAssessment.threshold.toFixed(3)} (
                {(currentAssessment.hybrid_anomaly_score - currentAssessment.threshold).toFixed(3)}{' '}
                relative)
              </p>
              <p className="technical text-xs">
                {currentAssessment.model_id} · {currentAssessment.feature_schema_version} ·{' '}
                {currentAssessment.calibration_method}
              </p>
            </div>
          ) : (
            <p className="text-sm text-slate-500">No streamed assessment yet.</p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <div>
            <p className="eyebrow">Explainable deviation</p>
            <h2 className="panel-title">Contributing Signals</h2>
          </div>
        </CardHeader>
        <CardContent>
          <p className="mb-3 text-xs text-slate-500">
            Contributing signals explain deviation from the synthetic normal baseline. They are not
            proof of malicious activity.
          </p>
          {currentAssessment?.contributing_signals.length ? (
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
              {currentAssessment.contributing_signals.map((signal) => (
                <li key={signal}>{signal}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">No contributing signals available.</p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <div>
            <p className="eyebrow">Auditable score inputs</p>
            <h2 className="panel-title">Component Breakdown</h2>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {Object.entries(componentLabels).map(([key, label]) => {
            const value = currentAssessment?.component_scores[key] ?? 0
            return (
              <div key={key}>
                <div className="flex justify-between text-xs text-slate-500">
                  <span>{label}</span>
                  <span>{value.toFixed(3)}</span>
                </div>
                <progress className="w-full" max="1" value={value}>
                  {value}
                </progress>
              </div>
            )
          })}
          <p className="text-xs text-slate-500">
            Component values are deviation scores, not probabilities.
          </p>
        </CardContent>
      </Card>
      <Card className="xl:col-span-2">
        <CardHeader>
          <div>
            <p className="eyebrow">Streamed values</p>
            <h2 className="panel-title">Anomaly Timeline</h2>
          </div>
        </CardHeader>
        <CardContent>
          {assessmentTimeline.length ? (
            <div className="h-64 min-h-56 min-w-80" aria-hidden="true">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={assessmentTimeline}>
                  <CartesianGrid stroke="#1e293b" />
                  <XAxis dataKey="sequence_number" />
                  <YAxis domain={[0, 1]} />
                  <Tooltip
                    labelFormatter={(value) =>
                      `Synthetic event sequence ${typeof value === 'number' ? value.toString() : typeof value === 'string' ? value : ''}`
                    }
                  />
                  <ReferenceLine
                    y={currentAssessment?.threshold ?? selectedModel?.calibrated_threshold ?? 0}
                    stroke="#f59e0b"
                    strokeDasharray="4 4"
                  />
                  <Line
                    type="monotone"
                    dataKey="hybrid_anomaly_score"
                    stroke="#22d3ee"
                    dot={{ r: 3, fill: '#22d3ee' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              The timeline will use streamed assessment values when detection playback begins.
            </p>
          )}
          <p className="text-xs text-slate-500">
            Text summary: {assessmentTimeline.length} assessments; {anomalous.length} anomalous;
            maximum score {maximum.toFixed(3)}.
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <div>
            <p className="eyebrow">Factual playback values</p>
            <h2 className="panel-title">Playback Summary</h2>
          </div>
        </CardHeader>
        <CardContent className="playback-facts">
          <div>
            <span>Events streamed</span>
            <strong>{events.length}</strong>
          </div>
          <div>
            <span>Assessments received</span>
            <strong>{assessmentTimeline.length}</strong>
          </div>
          <div>
            <span>Anomalous / normal</span>
            <strong>
              {anomalous.length} / {normal}
            </strong>
          </div>
          <div>
            <span>Maximum score</span>
            <strong>{maximum.toFixed(3)}</strong>
          </div>
          <div>
            <span>First anomalous sequence</span>
            <strong>{first?.sequence_number ?? 'none'}</strong>
          </div>
          <div>
            <span>Simulated seconds</span>
            <strong>{first ? simulatedElapsedSeconds : 'none'}</strong>
          </div>
          <div>
            <span>Selected model</span>
            <strong>{selectedModel?.model_id.slice(0, 8) ?? 'none'}</strong>
          </div>
          <div>
            <span>Playback state</span>
            <strong>State: {playbackState}</strong>
          </div>
        </CardContent>
      </Card>
    </>
  )
}
