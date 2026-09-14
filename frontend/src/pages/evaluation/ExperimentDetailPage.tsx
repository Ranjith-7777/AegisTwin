import { Fragment, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardHeader } from '../../components/ui/card'
import { toClientApiError } from '../../services/apiClient'
import { getExperiment, rerunExperiment } from '../../services/evaluationApi'
import {
  DEFENCE_MODE_LABELS,
  type ArsPillar,
  type ExperimentDetail,
  type Metric,
  type TimelineEventStatus,
} from '../../types/evaluation'

const PILLAR_LABELS: Record<string, string> = {
  A: 'Threat Awareness (A)',
  W: 'Withstand / Containment (W)',
  M: 'Mission Preservation (M)',
  R: 'Verified Recovery (R)',
}

const PILLAR_ORDER = ['A', 'W', 'M', 'R'] as const

const TIMELINE_STATUS_LABEL: Record<TimelineEventStatus, string> = {
  occurred: 'occurred',
  skipped_not_applicable: 'skipped — not applicable',
  failed: 'failed',
}

function metricLabel(key: string): string {
  return key.replaceAll('_', ' ')
}

function formatMetricValue(metric: Metric): string {
  if (!metric.applicable || metric.value === null) return 'N/A'
  if (typeof metric.value === 'boolean') return metric.value ? 'yes' : 'no'
  return typeof metric.value === 'number' ? metric.value.toFixed(3) : String(metric.value)
}

function formatRaw(value: unknown): string {
  if (value === null || value === undefined) return 'N/A'
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3)
  if (typeof value === 'string') return value
  return JSON.stringify(value)
}

function PillarBreakdown({ id, pillar }: { id: string; pillar: ArsPillar | undefined }) {
  const label = PILLAR_LABELS[id] ?? id
  if (!pillar) {
    return (
      <div className="rounded-md border border-slate-200 p-3">
        <p className="text-sm font-semibold">{label}</p>
        <p className="text-lg">N/A</p>
      </div>
    )
  }
  const value = pillar.applicable && pillar.value !== null ? pillar.value.toFixed(1) : 'N/A'
  return (
    <div className="rounded-md border border-slate-200 p-3">
      <p className="text-sm font-semibold">{label}</p>
      <p className="text-lg">{value}</p>
      {pillar.note ? <p className="text-xs text-slate-500">{pillar.note}</p> : null}
      {pillar.components ? (
        <details className="mt-2 text-xs text-slate-600">
          <summary className="cursor-pointer select-none">Raw components &amp; weights</summary>
          <div className="mt-1 space-y-1">
            {Object.entries(pillar.components).map(([key, component]) => (
              <p key={key}>
                {metricLabel(key)}: {formatRaw(component.raw_value)} (weight{' '}
                {component.weight.toFixed(2)}, effective {component.effective_weight.toFixed(3)}
                {component.applicable ? '' : ', N/A'})
              </p>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  )
}

export function ExperimentDetailPage() {
  const { experimentId } = useParams<{ experimentId: string }>()
  const navigate = useNavigate()
  const [experiment, setExperiment] = useState<ExperimentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [rerunning, setRerunning] = useState(false)
  const [rerunError, setRerunError] = useState<string | null>(null)

  useEffect(() => {
    if (!experimentId) return
    void getExperiment(experimentId)
      .then((data) => {
        setExperiment(data)
        setError(null)
      })
      .catch((cause: unknown) => {
        setError(toClientApiError(cause).message)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [experimentId])

  function handleRerun() {
    if (!experimentId) return
    setRerunning(true)
    setRerunError(null)
    void rerunExperiment(experimentId)
      .then((created) => {
        void navigate(`/evaluation/experiments/${created.experiment_id}`)
      })
      .catch((cause: unknown) => {
        setRerunError(toClientApiError(cause).message)
      })
      .finally(() => {
        setRerunning(false)
      })
  }

  if (loading) {
    return (
      <section aria-labelledby="experiment-detail-title">
        <p role="status">Loading experiment…</p>
      </section>
    )
  }

  if (error || !experiment) {
    return (
      <section aria-labelledby="experiment-detail-title">
        <p role="alert" className="text-red-700">
          {error ?? 'This experiment could not be found.'}
        </p>
        <Link to="/evaluation/experiments" className="card-link">
          Back to Experiments
        </Link>
      </section>
    )
  }

  const isControl = experiment.defence_mode === 'no_active_defence'
  const metrics = experiment.metrics
  const curve = experiment.mission_health_curve
  const chartData = curve.map((point) => ({
    time: Number(point.logical_time_sim.toFixed(2)),
    health: Number(point.mission_health.toFixed(4)),
    stage: point.stage,
  }))

  return (
    <section className="space-y-6" aria-labelledby="experiment-detail-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Evaluation · Experiment</p>
          <h1 id="experiment-detail-title">{experiment.scenario_name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge className={isControl ? 'chip-warn' : 'chip-muted'}>
              {isControl
                ? 'CONTROL — NO ACTIVE DEFENCE'
                : DEFENCE_MODE_LABELS[experiment.defence_mode]}
            </Badge>
            <Badge className="chip-muted">seed {experiment.seed}</Badge>
            <Badge className={experiment.status === 'completed' ? 'chip-healthy' : 'chip-muted'}>
              {experiment.status.replaceAll('_', ' ')}
            </Badge>
          </div>
          {isControl ? (
            <p className="mt-2 text-sm text-slate-600">
              Attack observed for evaluation; no mitigation is applied. This is an intended baseline
              run, not a failed or broken experiment.
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to={`/evaluation/experiments/${experiment.experiment_id}/report`}>
            <Button variant="outline">View report</Button>
          </Link>
          <Button disabled={rerunning} onClick={handleRerun}>
            {rerunning ? 'Re-running…' : 'Re-run experiment'}
          </Button>
        </div>
      </header>
      {rerunError ? (
        <p role="alert" className="text-red-700">
          {rerunError}
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <h2 className="panel-title">Provenance</h2>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-2 text-xs text-slate-500 sm:grid-cols-2 lg:grid-cols-4">
            <dt>Topology version</dt>
            <dd>{experiment.topology_version}</dd>
            <dt>Red scenario version</dt>
            <dd>{experiment.red_scenario_version}</dd>
            <dt>Metrics version</dt>
            <dd>{metrics?.metrics_version ?? 'N/A'}</dd>
            <dt>MCI version</dt>
            <dd>{metrics?.mci_version ?? 'N/A'}</dd>
            <dt>ARS version</dt>
            <dd>{metrics?.ars_version ?? 'N/A'}</dd>
            <dt>Experiment ID</dt>
            <dd>{experiment.experiment_id}</dd>
          </dl>
        </CardContent>
      </Card>

      {!metrics ? (
        <Card>
          <CardContent>
            <p>
              No metrics have been computed for this experiment yet
              {experiment.status !== 'completed'
                ? ' — it has not finished running.'
                : '. This is unexpected for a completed experiment; try reloading.'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <div>
                <h2 className="panel-title">Aegis Resilience Score</h2>
                <p className="text-xs text-slate-500">
                  Deterministic evaluation score, not a probability.
                </p>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-4xl font-semibold">
                {metrics.ars_total === null ? 'N/A' : `${metrics.ars_total.toFixed(1)} / 100`}
              </p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {PILLAR_ORDER.map((pillar) => (
                  <PillarBreakdown
                    key={pillar}
                    id={pillar}
                    pillar={metrics.ars_pillars?.[pillar]}
                  />
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <h2 className="panel-title">Mission Health</h2>
                <p className="text-xs text-slate-500">
                  Mission health over simulated time, by stage. Mission Continuity Index is a
                  separate summary figure, shown alongside the curve — not a point on it.
                </p>
              </div>
              <p className="text-sm">
                <strong>MCI:</strong> {metrics.mci === null ? 'N/A' : metrics.mci.toFixed(3)}
              </p>
            </CardHeader>
            <CardContent>
              {chartData.length === 0 ? (
                <p className="text-sm text-slate-500">No mission-health points were recorded.</p>
              ) : (
                <div className="h-64" aria-label="Mission health over simulated time">
                  <ResponsiveContainer width="100%" height="100%" minWidth={280} minHeight={224}>
                    <LineChart
                      data={chartData}
                      margin={{ top: 8, right: 12, left: -12, bottom: 0 }}
                    >
                      <CartesianGrid stroke="var(--color-slate-800, #e2e8f0)" vertical={false} />
                      <XAxis
                        dataKey="time"
                        stroke="var(--color-slate-600, #64748b)"
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                        label={{
                          value: 'simulated time (s)',
                          position: 'insideBottom',
                          offset: -2,
                          fontSize: 10,
                        }}
                      />
                      <YAxis
                        domain={[0, 1]}
                        stroke="var(--color-slate-600, #64748b)"
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                      />
                      <Tooltip
                        formatter={(value) =>
                          typeof value === 'number' ? value.toFixed(3) : value
                        }
                        labelFormatter={(label, payload) => {
                          const numericLabel =
                            typeof label === 'number' || typeof label === 'string' ? label : ''
                          const stage = payload[0]
                            ? (payload[0].payload as { stage: string }).stage
                            : null
                          return stage
                            ? `t=${String(numericLabel)}s · ${stage}`
                            : `t=${String(numericLabel)}s`
                        }}
                      />
                      <Line
                        type="monotone"
                        dataKey="health"
                        stroke="var(--state-healthy, #2563eb)"
                        strokeWidth={2}
                        dot={{ r: 3 }}
                        isAnimationActive={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
              {chartData.length > 0 ? (
                <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                  {curve.map((point) => (
                    <li key={point.sequence}>
                      t={point.logical_time_sim.toFixed(1)}s: {point.stage} (
                      {point.mission_health.toFixed(2)})
                    </li>
                  ))}
                </ul>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <h2 className="panel-title">Raw &amp; normalized metrics</h2>
            </CardHeader>
            <CardContent>
              <div className="grid gap-6 lg:grid-cols-2">
                <div>
                  <h3 className="text-sm font-semibold">Normalized metrics</h3>
                  <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-sm">
                    {Object.entries(metrics.normalized_metrics).map(([key, metric]) => (
                      <Fragment key={key}>
                        <dt title={!metric.applicable && metric.note ? metric.note : undefined}>
                          {metricLabel(key)}
                        </dt>
                        <dd>{formatMetricValue(metric)}</dd>
                      </Fragment>
                    ))}
                  </dl>
                </div>
                <div>
                  <h3 className="text-sm font-semibold">Raw metrics</h3>
                  <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-sm">
                    {Object.entries(metrics.raw_metrics).map(([key, value]) => (
                      <Fragment key={key}>
                        <dt>{metricLabel(key)}</dt>
                        <dd>{formatRaw(value)}</dd>
                      </Fragment>
                    ))}
                  </dl>
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      <Card>
        <CardHeader>
          <h2 className="panel-title">Timeline</h2>
        </CardHeader>
        <CardContent>
          {!experiment.timeline || experiment.timeline.events.length === 0 ? (
            <p className="text-sm text-slate-500">No timeline is available for this experiment.</p>
          ) : (
            <ol className="space-y-3">
              {experiment.timeline.events.map((event) => (
                <li
                  key={event.sequence}
                  className={`rounded-md border p-3 text-sm ${
                    event.status === 'occurred'
                      ? 'border-slate-300'
                      : event.status === 'failed'
                        ? 'border-amber-300 bg-amber-50'
                        : 'border-dashed border-slate-200 text-slate-400'
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <strong>{event.stage.replaceAll('_', ' ')}</strong>
                    <Badge
                      className={
                        event.status === 'occurred'
                          ? 'chip-healthy'
                          : event.status === 'failed'
                            ? 'chip-warn'
                            : 'chip-muted'
                      }
                    >
                      {TIMELINE_STATUS_LABEL[event.status]}
                    </Badge>
                  </div>
                  <p className="mt-1">{event.summary}</p>
                  {event.logical_time_sim !== null ? (
                    <p className="mt-1 text-xs text-slate-500">
                      t={event.logical_time_sim.toFixed(2)}s
                    </p>
                  ) : null}
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
