import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Badge } from '../../components/ui/badge'
import { Card, CardContent, CardHeader } from '../../components/ui/card'
import { toClientApiError } from '../../services/apiClient'
import {
  exportExperimentsCsvUrl,
  exportExperimentsJsonUrl,
  getExperimentMetrics,
  listExperiments,
} from '../../services/evaluationApi'
import {
  DEFENCE_MODE_LABELS,
  type DefenceMode,
  type ExperimentMetrics,
  type ExperimentStatus,
  type ExperimentView,
} from '../../types/evaluation'

const DEFENCE_MODES: DefenceMode[] = ['no_active_defence', 'rule_based', 'ml_assisted', 'agentic']
const STATUSES: ExperimentStatus[] = [
  'created',
  'running_attack',
  'detecting',
  'responding',
  'verifying',
  'completed',
  'failed',
]

function outcome(value: unknown): string {
  if (value === true) return 'yes'
  if (value === false) return 'no'
  return 'N/A'
}

function scoreOrNa(value: number | null | undefined, digits: number): string {
  return typeof value === 'number' ? value.toFixed(digits) : 'N/A'
}

export function ExperimentListPage() {
  const navigate = useNavigate()
  const [experiments, setExperiments] = useState<ExperimentView[]>([])
  const [metricsById, setMetricsById] = useState<Record<string, ExperimentMetrics | null>>({})
  const [scenarioFilter, setScenarioFilter] = useState('')
  const [seedFilter, setSeedFilter] = useState('')
  const [defenceModeFilter, setDefenceModeFilter] = useState<DefenceMode | ''>('')
  const [statusFilter, setStatusFilter] = useState<ExperimentStatus | ''>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void listExperiments({
      scenario_id: scenarioFilter || undefined,
      seed: seedFilter ? Number(seedFilter) : undefined,
      defence_mode: defenceModeFilter || undefined,
      status: statusFilter || undefined,
    })
      .then((rows) => {
        setExperiments(rows)
        setError(null)
        const completedIds = rows
          .filter((item) => item.status === 'completed')
          .map((item) => item.experiment_id)
        return Promise.all(
          completedIds.map((id) =>
            getExperimentMetrics(id)
              .then((metrics) => [id, metrics] as const)
              .catch(() => [id, null] as const),
          ),
        )
      })
      .then((pairs) => {
        setMetricsById(Object.fromEntries(pairs))
      })
      .catch((cause: unknown) => {
        setError(toClientApiError(cause).message)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [scenarioFilter, seedFilter, defenceModeFilter, statusFilter])

  const currentFilters = {
    scenario_id: scenarioFilter || undefined,
    seed: seedFilter ? Number(seedFilter) : undefined,
    defence_mode: defenceModeFilter || undefined,
    status: statusFilter || undefined,
  }

  return (
    <section className="space-y-6" aria-labelledby="experiment-list-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Evaluation · Experiments</p>
          <h1 id="experiment-list-title">Experiments</h1>
          <p>
            Every reproducible evaluation run: one scenario, one seed, one defence mode. Select a
            row to inspect its full metrics, Aegis Resilience Score, mission-health curve and
            timeline.
          </p>
        </div>
        <div className="flex gap-2">
          <a href={exportExperimentsCsvUrl(currentFilters)} download className="card-link text-sm">
            Export CSV
          </a>
          <a href={exportExperimentsJsonUrl(currentFilters)} download className="card-link text-sm">
            Export JSON
          </a>
        </div>
      </header>
      <Card>
        <CardHeader>
          <h2 className="panel-title">Filters</h2>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col text-xs text-slate-600">
              Scenario ID
              <input
                aria-label="Scenario filter"
                value={scenarioFilter}
                onChange={(event) => {
                  setScenarioFilter(event.target.value)
                }}
                className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
                placeholder="all scenarios"
              />
            </label>
            <label className="flex flex-col text-xs text-slate-600">
              Seed
              <input
                aria-label="Seed filter"
                value={seedFilter}
                onChange={(event) => {
                  setSeedFilter(event.target.value.replace(/[^0-9]/g, ''))
                }}
                className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
                placeholder="all seeds"
              />
            </label>
            <label className="flex flex-col text-xs text-slate-600">
              Defence mode
              <select
                aria-label="Defence mode filter"
                value={defenceModeFilter}
                onChange={(event) => {
                  setDefenceModeFilter(event.target.value as DefenceMode | '')
                }}
                className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
              >
                <option value="">All</option>
                {DEFENCE_MODES.map((mode) => (
                  <option key={mode} value={mode}>
                    {DEFENCE_MODE_LABELS[mode]}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col text-xs text-slate-600">
              Status
              <select
                aria-label="Status filter"
                value={statusFilter}
                onChange={(event) => {
                  setStatusFilter(event.target.value as ExperimentStatus | '')
                }}
                className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
              >
                <option value="">All</option>
                {STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {status.replaceAll('_', ' ')}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </CardContent>
      </Card>
      {error ? (
        <p role="alert" className="text-red-700">
          {error}
        </p>
      ) : null}
      {loading ? <p role="status">Loading experiments…</p> : null}
      {!loading && experiments.length === 0 && !error ? (
        <p>No experiments match this filter selection.</p>
      ) : null}
      {!loading && experiments.length > 0 ? (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-2">Scenario</th>
                  <th className="px-4 py-2">Seed</th>
                  <th className="px-4 py-2">Defence mode</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">ARS</th>
                  <th className="px-4 py-2">MCI</th>
                  <th className="px-4 py-2">Verified containment</th>
                  <th className="px-4 py-2">Rollback</th>
                  <th className="px-4 py-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {experiments.map((experiment) => {
                  const metrics = metricsById[experiment.experiment_id]
                  const rawMetrics = metrics?.raw_metrics as
                    { rollback_required?: unknown; rollback_success?: unknown } | undefined
                  const rollbackText = !rawMetrics?.rollback_required
                    ? rawMetrics?.rollback_required === false
                      ? 'not required'
                      : 'N/A'
                    : outcome(rawMetrics.rollback_success)
                  return (
                    <tr
                      key={experiment.experiment_id}
                      className="cursor-pointer border-b border-slate-100 hover:bg-slate-50"
                      onClick={() => {
                        void navigate(`/evaluation/experiments/${experiment.experiment_id}`)
                      }}
                    >
                      <td className="px-4 py-2">{experiment.scenario_name}</td>
                      <td className="px-4 py-2">{experiment.seed}</td>
                      <td className="px-4 py-2">
                        <Badge className="chip-muted">
                          {DEFENCE_MODE_LABELS[experiment.defence_mode]}
                        </Badge>
                      </td>
                      <td className="px-4 py-2">{experiment.status.replaceAll('_', ' ')}</td>
                      <td className="px-4 py-2">{scoreOrNa(metrics?.ars_total, 1)}</td>
                      <td className="px-4 py-2">{scoreOrNa(metrics?.mci, 3)}</td>
                      <td className="px-4 py-2">
                        {experiment.defence_mode === 'no_active_defence'
                          ? 'N/A'
                          : outcome(experiment.verification_status === 'successful_simulation')}
                      </td>
                      <td className="px-4 py-2">{rollbackText}</td>
                      <td className="px-4 py-2">
                        {new Date(experiment.created_at).toLocaleString()}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : null}
    </section>
  )
}
