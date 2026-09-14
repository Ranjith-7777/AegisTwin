import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardHeader } from '../../components/ui/card'
import { toClientApiError } from '../../services/apiClient'
import { listRedScenarios } from '../../services/purpleTeamApi'
import { compareModes } from '../../services/evaluationApi'
import type { RedScenarioSummary } from '../../types/purpleTeam'
import {
  ALL_DEFENCE_MODES,
  CANONICAL_SEEDS,
  DEFENCE_MODE_LABELS,
  type DefenceMode,
  type ModeComparisonResult,
} from '../../types/evaluation'

const KEY_CHART_METRICS = ['ars_total', 'mci', 'attack_path_reduction']

const METRIC_LABELS: Record<string, string> = {
  detection_coverage: 'Detection coverage',
  time_to_first_detection: 'Time to first detection (s)',
  time_to_containment: 'Time to containment (s)',
  time_to_verified_recovery: 'Time to verified recovery (s)',
  attack_path_reduction: 'Attack-path reduction',
  blast_radius_reduction: 'Blast-radius reduction',
  critical_exposure_reduction: 'Critical exposure reduction',
  operational_disruption: 'Operational disruption',
  verification_success: 'Verified containment',
  mci: 'Mission Continuity Index',
  ars_total: 'Aegis Resilience Score',
}

function metricLabel(key: string): string {
  return METRIC_LABELS[key] ?? key.replaceAll('_', ' ')
}

function formatCell(value: number | boolean | null): string {
  if (value === null) return 'N/A'
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  return Number.isInteger(value) ? String(value) : value.toFixed(3)
}

/** Best value per row: for booleans, `true` wins; for numbers, higher is
 * treated as better EXCEPT for the two metrics where lower is better
 * (time-to-* and operational disruption). Computed purely from the real
 * response values - never hardcoded to favour any one mode. */
function bestMode(row: ModeComparisonResult['rows'][number]): string | null {
  const lowerIsBetter = row.metric.startsWith('time_to_') || row.metric === 'operational_disruption'
  let best: { mode: string; value: number } | null = null
  for (const [mode, cell] of Object.entries(row.values)) {
    if (!cell.applicable || cell.value === null) continue
    const numeric = typeof cell.value === 'boolean' ? (cell.value ? 1 : 0) : cell.value
    if (best === null) {
      best = { mode, value: numeric }
      continue
    }
    const better = lowerIsBetter ? numeric < best.value : numeric > best.value
    if (better) best = { mode, value: numeric }
  }
  return best?.mode ?? null
}

export function ComparisonPage() {
  const [scenarios, setScenarios] = useState<RedScenarioSummary[]>([])
  const [scenarioId, setScenarioId] = useState('')
  const [seed, setSeed] = useState<number>(CANONICAL_SEEDS[0] ?? 17)
  const [result, setResult] = useState<ModeComparisonResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    void listRedScenarios()
      .then((rows) => {
        setScenarios(rows)
        const first = rows[0]
        if (first && !scenarioId) setScenarioId(first.scenario_id)
      })
      .catch(() => {
        // Scenario catalogue is a convenience dropdown only; the free-text
        // fallback below still lets the user type an id by hand.
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function submitComparison() {
    if (!scenarioId) return
    setLoading(true)
    setError(null)
    setSubmitted(true)
    void compareModes({ scenarioId, seed })
      .then((data) => {
        setResult(data)
      })
      .catch((cause: unknown) => {
        setError(toClientApiError(cause).message)
        setResult(null)
      })
      .finally(() => {
        setLoading(false)
      })
  }

  const chartData = result
    ? KEY_CHART_METRICS.map((metricKey) => {
        const row = result.rows.find((candidate) => candidate.metric === metricKey)
        const point: Record<string, string | number> = { metric: metricLabel(metricKey) }
        for (const mode of ALL_DEFENCE_MODES) {
          const cell = row?.values[mode]
          if (cell && cell.applicable && typeof cell.value === 'number') {
            point[mode] = cell.value
          }
        }
        return point
      })
    : []

  return (
    <section className="space-y-6" aria-labelledby="comparison-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Evaluation · Comparison</p>
          <h1 id="comparison-title">Defence-mode comparison</h1>
          <p>
            Compare all four defence strategies on the SAME scenario and seed, side by side. Real
            values only - a mode with no completed experiment for this scenario/seed shows &quot;No
            experiment&quot;, never a fabricated zero.
          </p>
        </div>
      </header>

      <Card>
        <CardHeader>
          <h2 className="panel-title">Select scenario &amp; seed</h2>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              submitComparison()
            }}
          >
            <label className="flex flex-col text-xs text-slate-600">
              Scenario
              {scenarios.length > 0 ? (
                <select
                  aria-label="Scenario"
                  value={scenarioId}
                  onChange={(event) => {
                    setScenarioId(event.target.value)
                  }}
                  className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
                >
                  {scenarios.map((scenario) => (
                    <option key={scenario.scenario_id} value={scenario.scenario_id}>
                      {scenario.name}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  aria-label="Scenario"
                  value={scenarioId}
                  onChange={(event) => {
                    setScenarioId(event.target.value)
                  }}
                  placeholder="scenario id"
                  className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
                />
              )}
            </label>
            <label className="flex flex-col text-xs text-slate-600">
              Seed
              <input
                aria-label="Seed"
                type="number"
                list="canonical-seeds"
                value={seed}
                onChange={(event) => {
                  setSeed(Number(event.target.value))
                }}
                className="mt-1 w-28 rounded-md border border-slate-300 px-2 py-1 text-sm"
              />
              <datalist id="canonical-seeds">
                {CANONICAL_SEEDS.map((canonicalSeed) => (
                  <option key={canonicalSeed} value={canonicalSeed} />
                ))}
              </datalist>
              <span className="mt-1 text-[0.65rem] text-slate-400">
                Canonical set: {CANONICAL_SEEDS.join(', ')} (any seed may be entered)
              </span>
            </label>
            <Button type="submit" disabled={!scenarioId || loading}>
              {loading ? 'Comparing…' : 'Compare modes'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {error ? (
        <p role="alert" className="text-red-700">
          {error}
        </p>
      ) : null}
      {loading ? <p role="status">Loading comparison…</p> : null}

      {!loading && submitted && !error && result && result.rows.length === 0 ? (
        <Card>
          <CardContent>
            <p>No experiments exist yet for this scenario/seed combination.</p>
          </CardContent>
        </Card>
      ) : null}

      {!loading && result && result.rows.length > 0 ? (
        <>
          {result.missing_modes.length > 0 ? (
            <p role="status" className="text-sm text-amber-700">
              No experiment found for:{' '}
              {result.missing_modes.map((m) => DEFENCE_MODE_LABELS[m as DefenceMode]).join(', ')}.
            </p>
          ) : null}

          <Card>
            <CardHeader>
              <h2 className="panel-title">Comparison table</h2>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Metric</th>
                    {ALL_DEFENCE_MODES.map((mode) => (
                      <th key={mode} className="px-3 py-2">
                        {DEFENCE_MODE_LABELS[mode]}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((row) => {
                    const winner = bestMode(row)
                    return (
                      <tr key={row.metric} className="border-b border-slate-100">
                        <td className="px-3 py-2 font-medium">{metricLabel(row.metric)}</td>
                        {ALL_DEFENCE_MODES.map((mode) => {
                          const cell = row.values[mode]
                          const missing = !cell
                          const text = missing
                            ? 'No experiment'
                            : cell.applicable
                              ? formatCell(cell.value)
                              : 'N/A'
                          const isBest = winner === mode && !missing && cell.applicable
                          return (
                            <td
                              key={mode}
                              className={`px-3 py-2 ${isBest ? 'bg-blue-50 font-semibold text-blue-900' : ''} ${missing ? 'italic text-slate-400' : ''}`}
                            >
                              {text}
                            </td>
                          )
                        })}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <h2 className="panel-title">Key metrics by defence mode</h2>
            </CardHeader>
            <CardContent>
              <div className="h-72" aria-label="Defence-mode comparison chart">
                <ResponsiveContainer width="100%" height="100%" minWidth={280} minHeight={240}>
                  <BarChart data={chartData}>
                    <CartesianGrid stroke="#e2e8f0" vertical={false} />
                    <XAxis dataKey="metric" fontSize={11} tickLine={false} />
                    <YAxis fontSize={11} tickLine={false} />
                    <Tooltip />
                    <Legend formatter={(value) => DEFENCE_MODE_LABELS[value as DefenceMode]} />
                    {ALL_DEFENCE_MODES.map((mode, index) => (
                      <Bar
                        key={mode}
                        dataKey={mode}
                        name={mode}
                        fill={['#94a3b8', '#f59e0b', '#0ea5e9', '#2563eb'][index]}
                      />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <h2 className="panel-title">Paired deltas</h2>
              <p className="text-xs text-slate-500">
                delta = compared − reference. Unpaired deltas are flagged, never presented as clean.
              </p>
            </CardHeader>
            <CardContent>
              {result.paired_deltas.length === 0 ? (
                <p className="text-sm text-slate-500">No paired deltas are available.</p>
              ) : (
                <ul className="space-y-2">
                  {result.paired_deltas.map((delta) => (
                    <li
                      key={`${delta.metric}-${delta.reference_mode}-${delta.compared_mode}`}
                      className="rounded-md border border-slate-200 p-3 text-sm"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span>
                          <strong>{metricLabel(delta.metric)}</strong>:{' '}
                          {DEFENCE_MODE_LABELS[delta.compared_mode as DefenceMode]} −{' '}
                          {DEFENCE_MODE_LABELS[delta.reference_mode as DefenceMode]} ={' '}
                          {delta.delta === null
                            ? 'N/A'
                            : `${delta.delta > 0 ? '+' : ''}${delta.delta.toFixed(3)}`}
                        </span>
                        <Badge className={delta.paired ? 'chip-healthy' : 'chip-warn'}>
                          {delta.paired ? 'fairness-confirmed' : 'unpaired'}
                        </Badge>
                      </div>
                      {!delta.paired ? (
                        <p role="alert" className="mt-2 text-xs text-amber-700">
                          This delta is NOT a fair paired comparison:{' '}
                          {delta.fairness_reasons.join('; ') || 'reason not specified'}.
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </section>
  )
}
