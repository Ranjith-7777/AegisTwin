import { useEffect, useState } from 'react'

import { Card, CardContent, CardHeader } from '../../components/ui/card'
import { Button } from '../../components/ui/button'
import { toClientApiError } from '../../services/apiClient'
import { aggregate } from '../../services/evaluationApi'
import { listRedScenarios } from '../../services/purpleTeamApi'
import type { RedScenarioSummary } from '../../types/purpleTeam'
import {
  ALL_DEFENCE_MODES,
  CANONICAL_SEEDS,
  DEFENCE_MODE_LABELS,
  type AggregateResultView,
  type DefenceMode,
} from '../../types/evaluation'

const SMALL_SAMPLE_THRESHOLD = 5

function metricLabel(key: string): string {
  return key.replaceAll('_', ' ')
}

function fmt(value: number | null, digits = 3): string {
  return value === null ? 'N/A' : value.toFixed(digits)
}

export function AggregatePage() {
  const [scenarios, setScenarios] = useState<RedScenarioSummary[]>([])
  const [scenarioId, setScenarioId] = useState('')
  const [defenceMode, setDefenceMode] = useState<DefenceMode | ''>('')
  const [selectedSeeds, setSelectedSeeds] = useState<number[]>([])
  const [result, setResult] = useState<AggregateResultView | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    void listRedScenarios()
      .then(setScenarios)
      .catch(() => {
        // Optional convenience dropdown only.
      })
  }, [])

  function toggleSeed(seed: number) {
    setSelectedSeeds((current) =>
      current.includes(seed) ? current.filter((value) => value !== seed) : [...current, seed],
    )
  }

  function submitAggregate() {
    setLoading(true)
    setError(null)
    setSubmitted(true)
    void aggregate({
      scenarioId: scenarioId || undefined,
      defenceMode: defenceMode || undefined,
      seeds: selectedSeeds.length > 0 ? selectedSeeds : undefined,
    })
      .then(setResult)
      .catch((cause: unknown) => {
        setError(toClientApiError(cause).message)
        setResult(null)
      })
      .finally(() => {
        setLoading(false)
      })
  }

  const scopeLabel = (() => {
    if (!result) return ''
    const parts: string[] = []
    if (scenarioId) parts.push(`scenario=${scenarioId}`)
    if (defenceMode) parts.push(`defence_mode=${DEFENCE_MODE_LABELS[defenceMode]}`)
    if (selectedSeeds.length > 0) parts.push(`seeds=${selectedSeeds.join(',')}`)
    const count = String(result.experiment_count)
    return parts.length > 0
      ? `Aggregated across ${count} completed experiment(s) matching: ${parts.join(', ')}`
      : `Aggregated across ${count} completed experiment(s) - all completed experiments (no filter applied)`
  })()

  return (
    <section className="space-y-6" aria-labelledby="aggregate-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Evaluation · Aggregate</p>
          <h1 id="aggregate-title">Aggregate results</h1>
          <p>
            Mean ± std across completed experiments. No significance or p-value claims are shown -
            this is a descriptive summary only.
          </p>
        </div>
      </header>

      <Card>
        <CardHeader>
          <h2 className="panel-title">Filters</h2>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-wrap items-end gap-4"
            onSubmit={(event) => {
              event.preventDefault()
              submitAggregate()
            }}
          >
            <label className="flex flex-col text-xs text-slate-600">
              Scenario (optional)
              {scenarios.length > 0 ? (
                <select
                  aria-label="Scenario filter"
                  value={scenarioId}
                  onChange={(event) => {
                    setScenarioId(event.target.value)
                  }}
                  className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
                >
                  <option value="">All scenarios</option>
                  {scenarios.map((scenario) => (
                    <option key={scenario.scenario_id} value={scenario.scenario_id}>
                      {scenario.name}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  aria-label="Scenario filter"
                  value={scenarioId}
                  onChange={(event) => {
                    setScenarioId(event.target.value)
                  }}
                  placeholder="all scenarios"
                  className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
                />
              )}
            </label>
            <label className="flex flex-col text-xs text-slate-600">
              Defence mode (optional)
              <select
                aria-label="Defence mode filter"
                value={defenceMode}
                onChange={(event) => {
                  setDefenceMode(event.target.value as DefenceMode | '')
                }}
                className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
              >
                <option value="">All modes</option>
                {ALL_DEFENCE_MODES.map((mode) => (
                  <option key={mode} value={mode}>
                    {DEFENCE_MODE_LABELS[mode]}
                  </option>
                ))}
              </select>
            </label>
            <fieldset className="flex flex-col text-xs text-slate-600">
              <legend>Seeds (optional, default all)</legend>
              <div className="mt-1 flex flex-wrap gap-2">
                {CANONICAL_SEEDS.map((seed) => (
                  <label key={seed} className="flex items-center gap-1">
                    <input
                      type="checkbox"
                      aria-label={`Seed ${String(seed)}`}
                      checked={selectedSeeds.includes(seed)}
                      onChange={() => {
                        toggleSeed(seed)
                      }}
                    />
                    {seed}
                  </label>
                ))}
              </div>
            </fieldset>
            <Button type="submit" disabled={loading}>
              {loading ? 'Aggregating…' : 'Aggregate'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {error ? (
        <p role="alert" className="text-red-700">
          {error}
        </p>
      ) : null}
      {loading ? <p role="status">Loading aggregate…</p> : null}

      {!loading && submitted && !error && result && result.experiment_count === 0 ? (
        <Card>
          <CardContent>
            <p>No completed experiments match this filter selection.</p>
          </CardContent>
        </Card>
      ) : null}

      {!loading && result && result.experiment_count > 0 ? (
        <>
          <p className="text-sm font-medium text-slate-700">{scopeLabel}</p>

          <Card>
            <CardHeader>
              <h2 className="panel-title">Numeric metrics (mean ± std)</h2>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Metric</th>
                    <th className="px-3 py-2">Mean ± std</th>
                    <th className="px-3 py-2">Median</th>
                    <th className="px-3 py-2">Min</th>
                    <th className="px-3 py-2">Max</th>
                    <th className="px-3 py-2">n applicable</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(result.metric_summaries).map(([key, summary]) => (
                    <tr key={key} className="border-b border-slate-100">
                      <td className="px-3 py-2 font-medium">{metricLabel(key)}</td>
                      <td className="px-3 py-2">
                        {summary.mean === null
                          ? 'N/A'
                          : `${fmt(summary.mean)} ± ${fmt(summary.std)}`}
                      </td>
                      <td className="px-3 py-2">{fmt(summary.median)}</td>
                      <td className="px-3 py-2">{fmt(summary.minimum)}</td>
                      <td className="px-3 py-2">{fmt(summary.maximum)}</td>
                      <td className="px-3 py-2">
                        {summary.n_applicable}
                        {summary.n_applicable > 0 &&
                        summary.n_applicable <= SMALL_SAMPLE_THRESHOLD ? (
                          <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-[0.65rem] font-semibold uppercase text-amber-800">
                            small sample
                          </span>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <h2 className="panel-title">Boolean outcomes</h2>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Outcome</th>
                    <th className="px-3 py-2">Success / total applicable</th>
                    <th className="px-3 py-2">Success rate</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(result.boolean_summaries).map(([key, summary]) => (
                    <tr key={key} className="border-b border-slate-100">
                      <td className="px-3 py-2 font-medium">{metricLabel(key)}</td>
                      <td className="px-3 py-2">
                        {summary.success_count} / {summary.total_applicable}
                        {summary.total_applicable > 0 &&
                        summary.total_applicable <= SMALL_SAMPLE_THRESHOLD ? (
                          <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-[0.65rem] font-semibold uppercase text-amber-800">
                            small sample
                          </span>
                        ) : null}
                      </td>
                      <td className="px-3 py-2">
                        {summary.success_rate === null
                          ? 'N/A'
                          : `${(summary.success_rate * 100).toFixed(0)}%`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      ) : null}
    </section>
  )
}
