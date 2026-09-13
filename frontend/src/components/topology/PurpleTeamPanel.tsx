import { useEffect, useState } from 'react'

import { Card, CardContent, CardHeader } from '../ui/card'
import { Button } from '../ui/button'
import {
  getScenarioDefinition,
  listRedScenarios,
  runPurpleTeamExperiment,
} from '../../services/purpleTeamApi'
import { toClientApiError } from '../../services/apiClient'
import type {
  PurpleExperimentMode,
  PurpleTeamExperiment,
  RedScenarioSummary,
} from '../../types/purpleTeam'
import type { RedScenarioDefinition } from '../../types/redScenario'

const OUTCOME_CHIP: Record<string, string> = {
  succeeded_synthetic: 'chip-warn',
  failed_precondition: 'chip-muted',
  blocked_synthetic: 'chip-healthy',
  attempted: 'chip-muted',
  skipped: 'chip-muted',
}

function defenseResponseFor(step: {
  response_recommendation_id: string | null
  orchestration_state: string | null
}): string {
  if (!step.response_recommendation_id) return '—'
  if (step.orchestration_state === 'verified') return 'Verified'
  if (step.orchestration_state === 'completed_simulated') return 'Executed'
  if (step.orchestration_state) return step.orchestration_state.replace(/_/g, ' ')
  return 'Recommended'
}

export function PurpleTeamPanel() {
  const [scenarios, setScenarios] = useState<RedScenarioSummary[]>([])
  const [scenarioId, setScenarioId] = useState('credential-compromise')
  const [definition, setDefinition] = useState<RedScenarioDefinition | null>(null)
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

  useEffect(() => {
    void getScenarioDefinition(scenarioId)
      .then(setDefinition)
      .catch(() => {
        setDefinition(null)
      })
  }, [scenarioId])

  function run() {
    setLoading(true)
    setError(null)
    setExperiment(null)
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

        {definition ? (
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
            <p className="font-semibold text-slate-800">{definition.display_name}</p>
            <p className="mt-1">{definition.objective}</p>
            <p className="mt-1 text-slate-500">
              Entry point: <strong>{definition.initial_access_point}</strong>
              {definition.high_value_objective ? (
                <>
                  {' '}
                  · High-value objective: <strong>{definition.high_value_objective}</strong>
                </>
              ) : null}
              {' · '}
              {definition.steps.length} step(s)
            </p>
          </div>
        ) : null}

        {loading ? (
          <div className="flex items-center gap-2 text-sm text-slate-600" aria-live="polite">
            <span
              className="size-3 animate-spin rounded-full border-2 border-slate-300 border-t-blue-600"
              aria-hidden="true"
            />
            Running experiment: simulating scenario, training/scoring detection, correlating
            evidence, and orchestrating response if enabled…
          </div>
        ) : null}
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
              <>
                <div className="playback-facts">
                  <div>
                    <span>Attempted steps</span>
                    <strong>{experiment.summary.attempted_steps}</strong>
                  </div>
                  <div>
                    <span>Detected steps</span>
                    <strong>{experiment.summary.detected_steps}</strong>
                  </div>
                  <div>
                    <span>Missed (expected-detectable)</span>
                    <strong>
                      {experiment.summary.missed_steps} /{' '}
                      {experiment.summary.expected_detectable_steps}
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
                  <div>
                    <span>Verification result</span>
                    <strong>{experiment.summary.verification_result ?? 'n/a'}</strong>
                  </div>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <div>
                    <p className="text-xs font-semibold text-slate-600">
                      ATT&amp;CK techniques exercised
                    </p>
                    <p className="text-xs text-slate-500">
                      {experiment.summary.mitre_techniques_exercised.join(', ') || '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-slate-600">
                      ATT&amp;CK techniques observed
                    </p>
                    <p className="text-xs text-slate-500">
                      {experiment.summary.mitre_techniques_observed.join(', ') || '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-slate-600">
                      Critical assets reached (real evidence)
                    </p>
                    <p className="text-xs text-slate-500">
                      {experiment.summary.critical_assets_reached.join(', ') || 'none observed'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-slate-600">
                      Estimated synthetic blast radius
                    </p>
                    <p className="text-xs text-slate-500">
                      {experiment.summary.blast_radius_context ? (
                        <>
                          {experiment.summary.blast_radius_context.reachable_count} reachable ·{' '}
                          {experiment.summary.blast_radius_context.critical_assets_at_risk.length}{' '}
                          critical at risk ·{' '}
                          {experiment.summary.blast_radius_context.trust_zones_reached.length}{' '}
                          zone(s) · score {experiment.summary.blast_radius_context.score.toFixed(1)}
                          /100 ({experiment.summary.blast_radius_context.mode.replace('_', ' ')})
                        </>
                      ) : (
                        'not computed'
                      )}
                    </p>
                  </div>
                </div>
                {experiment.summary.attack_path_context ? (
                  <div className="rounded-md border border-slate-200 p-3 text-xs text-slate-600">
                    <p className="font-semibold text-slate-700">Attack path context</p>
                    <p className="mt-1">{experiment.summary.attack_path_context.statement}</p>
                  </div>
                ) : null}
              </>
            ) : null}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-slate-500">
                    <th className="py-1 pr-2">#</th>
                    <th className="py-1 pr-2">Red action</th>
                    <th className="py-1 pr-2">ATT&amp;CK</th>
                    <th className="py-1 pr-2">Target</th>
                    <th className="py-1 pr-2">Result</th>
                    <th className="py-1 pr-2">Detected?</th>
                    <th className="py-1 pr-2">Incident/evidence</th>
                    <th className="py-1 pr-2">Defense response</th>
                  </tr>
                </thead>
                <tbody>
                  {experiment.steps.map((step) => (
                    <tr key={step.step_result_id} className="border-t border-slate-100">
                      <td className="py-1 pr-2">{step.step_sequence}</td>
                      <td className="py-1 pr-2">{step.description}</td>
                      <td className="py-1 pr-2">{step.expected_technique_id ?? '—'}</td>
                      <td className="py-1 pr-2">{step.target_asset_id ?? '—'}</td>
                      <td className="py-1 pr-2">
                        <span className={`chip ${OUTCOME_CHIP[step.outcome] ?? 'chip-muted'}`}>
                          {step.outcome.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="py-1 pr-2">{step.detected ? 'Yes' : 'No'}</td>
                      <td className="py-1 pr-2">
                        {step.incident_candidate_id ? step.incident_candidate_id.slice(0, 8) : '—'}
                      </td>
                      <td className="py-1 pr-2">{defenseResponseFor(step)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
