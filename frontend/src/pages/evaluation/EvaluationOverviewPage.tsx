import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Badge } from '../../components/ui/badge'
import { Card, CardContent, CardHeader } from '../../components/ui/card'
import { toClientApiError } from '../../services/apiClient'
import { getExperimentMetrics, listBatches, listExperiments } from '../../services/evaluationApi'
import { DEFENCE_MODE_LABELS, type BatchView, type ExperimentView } from '../../types/evaluation'

function mean(values: number[]): number | null {
  if (values.length === 0) return null
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

export function EvaluationOverviewPage() {
  const [experiments, setExperiments] = useState<ExperimentView[]>([])
  const [batches, setBatches] = useState<BatchView[]>([])
  const [arsValues, setArsValues] = useState<number[]>([])
  const [mciValues, setMciValues] = useState<number[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void Promise.all([listExperiments(), listBatches()])
      .then(([experimentRows, batchRows]) => {
        setExperiments(experimentRows)
        setBatches(batchRows)
        setError(null)
        const completedIds = experimentRows
          .filter((item) => item.status === 'completed')
          .map((item) => item.experiment_id)
        return Promise.all(completedIds.map((id) => getExperimentMetrics(id).catch(() => null)))
      })
      .then((metricsRows) => {
        setArsValues(
          metricsRows
            .map((metrics) => metrics?.ars_total)
            .filter((value): value is number => typeof value === 'number'),
        )
        setMciValues(
          metricsRows
            .map((metrics) => metrics?.mci)
            .filter((value): value is number => typeof value === 'number'),
        )
      })
      .catch((cause: unknown) => {
        setError(toClientApiError(cause).message)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [])

  const meanArs = mean(arsValues)
  const meanMci = mean(mciValues)

  const completed = experiments.filter((item) => item.status === 'completed')
  const scenarioIds = new Set(experiments.map((item) => item.scenario_id))
  const seeds = new Set(experiments.map((item) => item.seed))
  const defenceModes = new Set(experiments.map((item) => item.defence_mode))
  const verificationApplicable = completed.filter(
    (item) => item.defence_mode !== 'no_active_defence' && item.verification_status !== null,
  )
  const verifiedSuccessCount = verificationApplicable.filter(
    (item) => item.verification_status === 'successful_simulation',
  ).length
  const verifiedRate =
    verificationApplicable.length > 0 ? verifiedSuccessCount / verificationApplicable.length : null

  const latestBatch = batches
    .slice()
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0]

  return (
    <section className="space-y-6" aria-labelledby="evaluation-overview-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Evaluation</p>
          <h1 id="evaluation-overview-title">Evaluation Overview</h1>
          <p>
            A summary of real, persisted experiments - deterministic scenario/seed/defence-mode runs
            with computed metrics, MCI and Aegis Resilience Score. No projected or estimated
            figures.
          </p>
        </div>
      </header>
      {error ? (
        <p role="alert" className="text-red-700">
          {error}
        </p>
      ) : null}
      {loading ? <p role="status">Loading evaluation summary…</p> : null}
      {!loading && experiments.length === 0 && !error ? (
        <Card>
          <CardContent>
            <p>
              No experiments have been run yet. Create one from{' '}
              <Link to="/evaluation/experiments" className="card-link">
                Experiments
              </Link>
              .
            </p>
          </CardContent>
        </Card>
      ) : null}
      {!loading && experiments.length > 0 ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader>
                <h2 className="panel-title">Total experiments</h2>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold">{experiments.length}</p>
                <p className="text-xs text-slate-500">{completed.length} completed</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <h2 className="panel-title">Scenarios evaluated</h2>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold">{scenarioIds.size}</p>
                <p className="text-xs text-slate-500">{seeds.size} distinct seed(s)</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <h2 className="panel-title">Defence modes present</h2>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1">
                  {[...defenceModes].map((mode) => (
                    <Badge key={mode} className="chip-muted">
                      {DEFENCE_MODE_LABELS[mode]}
                    </Badge>
                  ))}
                  {defenceModes.size === 0 ? (
                    <span className="text-sm text-slate-500">none</span>
                  ) : null}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <h2 className="panel-title">Verified containment rate</h2>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold">
                  {verifiedRate === null ? 'N/A' : `${(verifiedRate * 100).toFixed(0)}%`}
                </p>
                <p className="text-xs text-slate-500">
                  across {verificationApplicable.length} completed experiment(s) where verification
                  applies (excludes no-active-defence controls)
                </p>
              </CardContent>
            </Card>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <h2 className="panel-title">Mean Aegis Resilience Score</h2>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold">
                  {meanArs === null ? 'N/A' : `${meanArs.toFixed(1)} / 100`}
                </p>
                <p className="text-xs text-slate-500">
                  across {arsValues.length} completed experiment(s) with a computed score (N/A
                  experiments excluded from this average)
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <h2 className="panel-title">Mean Mission Continuity Index</h2>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold">
                  {meanMci === null ? 'N/A' : meanMci.toFixed(3)}
                </p>
                <p className="text-xs text-slate-500">
                  across {mciValues.length} completed experiment(s) with a computed MCI (N/A
                  experiments excluded from this average)
                </p>
              </CardContent>
            </Card>
          </div>
          <Card>
            <CardHeader>
              <h2 className="panel-title">Latest batch</h2>
              <Link to="/evaluation/experiments" className="card-link">
                View experiments
              </Link>
            </CardHeader>
            <CardContent>
              {latestBatch ? (
                <p>
                  Batch {latestBatch.batch_id.slice(0, 8)}: {latestBatch.completed_count}/
                  {latestBatch.total_experiments} completed
                  {latestBatch.failed_count > 0
                    ? `, ${String(latestBatch.failed_count)} failed`
                    : ''}{' '}
                  · {latestBatch.status}
                </p>
              ) : (
                <p>No batches have been run yet.</p>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </section>
  )
}
