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
import { compareModes, createExperiment } from '../../services/evaluationApi'
import { useOptionalAutonomyWorkflow } from '../../hooks/useAutonomyWorkflow'
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
  false_positive_rate: 'False-positive rate',
  time_to_first_detection: 'Time to first detection (logical s)',
  time_to_incident: 'Time to incident (logical s)',
  time_to_response: 'Time to response (logical s)',
  time_to_containment: 'Time to containment (logical s)',
  time_to_verified_recovery: 'Time to verified recovery (logical s)',
  containment_success: 'Containment success',
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
  const lowerIsBetter =
    row.metric.startsWith('time_to_') ||
    row.metric === 'operational_disruption' ||
    row.metric === 'false_positive_rate'
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

const MODE_COLORS: Record<DefenceMode, string> = {
  no_active_defence: '#64748b',
  rule_based: '#fbbf24',
  ml_assisted: '#38bdf8',
  agentic: '#34d399',
}

function cellValue(result: ModeComparisonResult, metric: string, mode: string) {
  const cell = result.rows.find((row) => row.metric === metric)?.values[mode]
  return cell?.applicable ? cell.value : null
}

export function ComparisonPage() {
  const [scenarios, setScenarios] = useState<RedScenarioSummary[]>([])
  const [scenarioId, setScenarioId] = useState('')
  const [seed, setSeed] = useState<number>(84)
  const [running, setRunning] = useState<string | null>(null)
  const workflow = useOptionalAutonomyWorkflow()
  const canOperate = workflow?.session?.can_operate ?? true
  const [result, setResult] = useState<ModeComparisonResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    void listRedScenarios()
      .then((rows) => {
        setScenarios(rows)
        const preferred =
          rows.find((row) => row.scenario_id === 'staged-compromise-demo') ?? rows[0]
        if (preferred && !scenarioId) setScenarioId(preferred.scenario_id)
      })
      .catch(() => {
        // Scenario catalogue is a convenience dropdown only; the free-text
        // fallback below still lets the user type an id by hand.
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /** Create one experiment per defence mode that has none for this scenario
   * and seed, then compare - the "same attack, four defenders" experiment. */
  async function runAllStrategies() {
    if (!scenarioId) return
    setError(null)
    try {
      const existing = await compareModes({ scenarioId, seed })
      const missing = ALL_DEFENCE_MODES.filter((mode) => !existing.available_modes.includes(mode))
      for (const mode of missing) {
        setRunning(DEFENCE_MODE_LABELS[mode])
        await createExperiment({ scenario_id: scenarioId, seed, defence_mode: mode })
      }
    } catch (cause) {
      setError(toClientApiError(cause).message)
    } finally {
      setRunning(null)
    }
    submitComparison()
  }

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
          <p className="eyebrow">Analysis · Evaluation</p>
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
            <Button type="submit" variant="outline" disabled={!scenarioId || loading}>
              {loading ? 'Comparing…' : 'Compare modes'}
            </Button>
            <Button
              type="button"
              disabled={!scenarioId || loading || running !== null || !canOperate}
              title={canOperate ? undefined : 'Running experiments requires the ANALYST role.'}
              onClick={() => void runAllStrategies()}
            >
              {running ? `Running ${running}…` : 'Run all four strategies'}
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

          <div className="split-3 !grid-cols-4" aria-label="Strategy outcomes">
            {ALL_DEFENCE_MODES.map((mode) => {
              const present = result.available_modes.includes(mode)
              const ars = cellValue(result, 'ars_total', mode)
              const mci = cellValue(result, 'mci', mode)
              const contained = cellValue(result, 'containment_success', mode)
              const verified = cellValue(result, 'verification_success', mode)
              return (
                <div
                  key={mode}
                  className="panel p-3"
                  style={{ borderTop: `2px solid ${MODE_COLORS[mode]}` }}
                >
                  <p className="m-0 text-[0.8rem] font-semibold text-[var(--text)]">
                    {DEFENCE_MODE_LABELS[mode]}
                  </p>
                  {present ? (
                    <div className="mt-2 grid grid-cols-2 gap-2">
                      <div className="metric">
                        <span className="metric-label">ARS</span>
                        <span className="metric-value is-sm">
                          {typeof ars === 'number' ? ars.toFixed(1) : 'N/A'}
                        </span>
                      </div>
                      <div className="metric">
                        <span className="metric-label">MCI</span>
                        <span className="metric-value is-sm">
                          {typeof mci === 'number' ? mci.toFixed(3) : 'N/A'}
                        </span>
                      </div>
                      <div className="metric">
                        <span className="metric-label">Contained</span>
                        <span
                          className={`metric-value is-sm ${contained === true ? 'tone-ok' : ''}`}
                        >
                          {contained === null ? 'N/A' : contained ? 'yes' : 'no'}
                        </span>
                      </div>
                      <div className="metric">
                        <span className="metric-label">Verified</span>
                        <span
                          className={`metric-value is-sm ${verified === true ? 'tone-ok' : ''}`}
                        >
                          {verified === null ? 'N/A' : verified ? 'yes' : 'no'}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <p className="m-0 mt-2 text-[0.75rem] italic text-[var(--text-faint)]">
                      No experiment
                    </p>
                  )}
                </div>
              )
            })}
          </div>
          {(() => {
            const values = result.available_modes
              .map((mode) => cellValue(result, 'mci', mode))
              .filter((value): value is number => typeof value === 'number')
            return values.length > 1 && values.every((value) => value === values[0]) ? (
              <p className="notice is-warn m-0" role="note">
                MCI is identical ({values[0]?.toFixed(3)}) for every strategy here, so it does not
                discriminate between them for this scenario: evidence exposure saturates the compact
                synthetic topology at the first anomaly, and evaluation responses land at the end of
                the replay, leaving no post-recovery interval to credit. Compare containment,
                verification and ARS instead. This is a documented property of the bundled
                environment, not a measurement failure.
              </p>
            ) : null
          })()}
          <p className="m-0 text-[0.74rem] text-[var(--text-faint)]">
            Times are logical (simulated) seconds on the replayed scenario timeline - not real-world
            latency. ARS = Aegis Resilience Score, MCI = Mission Continuity Index.
          </p>

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
                    <CartesianGrid vertical={false} />
                    <XAxis dataKey="metric" fontSize={11} tickLine={false} />
                    <YAxis fontSize={11} tickLine={false} />
                    <Tooltip cursor={{ fill: 'rgba(148,163,184,0.08)' }} />
                    <Legend formatter={(value) => DEFENCE_MODE_LABELS[value as DefenceMode]} />
                    {ALL_DEFENCE_MODES.map((mode) => (
                      <Bar key={mode} dataKey={mode} name={mode} fill={MODE_COLORS[mode]} />
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
