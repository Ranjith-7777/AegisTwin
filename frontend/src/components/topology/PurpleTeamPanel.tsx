import { useEffect, useState } from 'react'

import { Card, CardContent, CardHeader } from '../ui/card'
import { Button } from '../ui/button'
import { listRedScenarios, runPurpleTeamExperiment } from '../../services/purpleTeamApi'
import { toClientApiError } from '../../services/apiClient'
import type {
  PurpleExperimentMode,
  PurpleTeamExperiment,
  RedScenarioSummary,
} from '../../types/purpleTeam'

const OUTCOME_CHIP: Record<string, string> = {
  succeeded_synthetic: 'chip-warn',
  failed_precondition: 'chip-muted',
  blocked_synthetic: 'chip-healthy',
  attempted: 'chip-muted',
  skipped: 'chip-muted',
}

export function PurpleTeamPanel() {
  const [scenarios, setScenarios] = useState<RedScenarioSummary[]>([])
  const [scenarioId, setScenarioId] = useState('credential-compromise')
  const [mode, setMode] = useState<PurpleExperimentMode>('observe_only')
  const [seed, setSeed] = useState(84)
  const [experiment, setExperiment] = useState<PurpleTeamExperiment | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void listRedScenarios()
      .then(setScenarios)
      .catch(() => undefined)
  }, [])

  function run() {
    setLoading(true)
    setError(null)
    void runPurpleTeamExperiment({ scenarioId, mode, seed })
      .then(setExperiment)
      .catch((cause: unknown) => {
        setExperiment(null)
        setError(toClientApiError(cause).message)
      })
      .finally(() => {
        setLoading(false)
      })
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <h2 className="panel-title">Purple Team Experiment</h2>
          <p className="text-xs text-slate-500">
            Runs one Red scenario through the real simulation → detection → correlation → prediction
            → (optionally) response/orchestration pipeline. Detection is never treated as
            prevention. See docs/architecture/PURPLE_TEAM.md.
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col text-xs text-slate-600">
            Scenario
            <select
              className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
              value={scenarioId}
              onChange={(event) => {
                setScenarioId(event.target.value)
              }}
            >
              {scenarios.map((item) => (
                <option key={item.scenario_id} value={item.scenario_id}>
                  {item.name}
                  {item.is_red_agent_scenario ? ' (Red agent)' : ''}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-xs text-slate-600">
            Mode
            <select
              className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
              value={mode}
              onChange={(event) => {
                setMode(event.target.value as PurpleExperimentMode)
              }}
            >
              <option value="observe_only">Observe only</option>
              <option value="defense_enabled">Defense enabled</option>
            </select>
          </label>
          <label className="flex flex-col text-xs text-slate-600">
            Seed
            <input
              type="number"
              className="mt-1 w-24 rounded-md border border-slate-300 px-2 py-1 text-sm"
              value={seed}
              onChange={(event) => {
                setSeed(Number(event.target.value) || 84)
              }}
            />
          </label>
          <Button onClick={run} disabled={loading}>
            {loading ? 'Running…' : 'Run experiment'}
          </Button>
        </div>
        {error ? (
          <p className="text-red-700" role="alert">
            {error}
          </p>
        ) : null}
        {experiment ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="chip chip-accent">{experiment.status}</span>
              <span className="chip chip-muted">{experiment.mode.replace(/_/g, ' ')}</span>
              {experiment.summary ? (
                <span className="chip chip-muted">Outcome: {experiment.summary.final_outcome}</span>
              ) : null}
            </div>
            {experiment.summary ? (
              <div className="playback-facts">
                <div>
                  <span>Detected / expected-detectable</span>
                  <strong>
                    {experiment.summary.detected_steps} / {experiment.summary.total_steps}
                  </strong>
                </div>
                <div>
                  <span>Detection coverage</span>
                  <strong>
                    {experiment.summary.detection_step_coverage !== null
                      ? `${String(Math.round(experiment.summary.detection_step_coverage * 100))}%`
                      : 'n/a'}
                  </strong>
                </div>
                <div>
                  <span>Incident created</span>
                  <strong>{experiment.summary.incident_created ? 'Yes' : 'No'}</strong>
                </div>
                <div>
                  <span>Response executed</span>
                  <strong>{experiment.summary.response_executed ? 'Yes' : 'No'}</strong>
                </div>
              </div>
            ) : null}
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-slate-500">
                  <th className="py-1 pr-2">#</th>
                  <th className="py-1 pr-2">Step</th>
                  <th className="py-1 pr-2">Expected technique</th>
                  <th className="py-1 pr-2">Outcome</th>
                  <th className="py-1 pr-2">Detected</th>
                </tr>
              </thead>
              <tbody>
                {experiment.steps.map((step) => (
                  <tr key={step.step_result_id} className="border-t border-slate-100">
                    <td className="py-1 pr-2">{step.step_sequence}</td>
                    <td className="py-1 pr-2">{step.description}</td>
                    <td className="py-1 pr-2">{step.expected_technique_id ?? '—'}</td>
                    <td className="py-1 pr-2">
                      <span className={`chip ${OUTCOME_CHIP[step.outcome] ?? 'chip-muted'}`}>
                        {step.outcome.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="py-1 pr-2">{step.detected ? 'Yes' : 'No'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
