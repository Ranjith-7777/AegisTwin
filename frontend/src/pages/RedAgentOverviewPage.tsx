import { CircleAlert, FlaskConical, Pause, Play, RotateCcw, Square, Swords } from 'lucide-react'
import { useEffect, useMemo, useState, type SyntheticEvent } from 'react'
import { Link } from 'react-router-dom'

import { LiveEventStream } from '../components/simulation/LiveEventStream'
import { RunHistory } from '../components/simulation/RunHistory'
import { Button } from '../components/ui/button'
import { Bar, KeyValue } from '../components/ui/panel'
import { useAutonomyWorkflow } from '../hooks/useAutonomyWorkflow'
import { useSimulationPlayback } from '../hooks/useSimulationPlayback'
import { DEMO_MODE } from '../lib/constants'
import { cn } from '../lib/utils'
import { toClientApiError } from '../services/apiClient'
import { trainDetectionModel } from '../services/detectionApi'
import { getScenarioDefinition, listRedScenarios } from '../services/purpleTeamApi'
import type { RedScenarioSummary } from '../types/purpleTeam'
import type { RedScenarioDefinition } from '../types/redScenario'
import type { SimulationScenario } from '../types/simulation'

const SEVERITY_ORDER = ['informational', 'low', 'medium', 'high', 'critical']
const SPEEDS = [1, 5, 10, 20, 50]
const DEFAULT_SCENARIO = 'staged-compromise-demo'

/** The same deterministic configuration the demo launcher bootstraps. */
const DEMO_MODEL_REQUEST = {
  training_seed_range: { start: 1, end: 5 },
  validation_seed_range: { start: 6, end: 10 },
  evaluation_seed_range: { start: 11, end: 13 },
  random_state: 17,
  target_false_positive_rate: 0.1,
  n_estimators: 100,
}

function peakSeverity(scenario: SimulationScenario): string {
  return scenario.steps.reduce(
    (peak, step) =>
      SEVERITY_ORDER.indexOf(step.severity) > SEVERITY_ORDER.indexOf(peak) ? step.severity : peak,
    'informational',
  )
}

function duration(scenario: SimulationScenario): number {
  return Math.max(0, ...scenario.steps.map((step) => step.offset_seconds))
}

function clock(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  return `${String(minutes)}:${String(seconds % 60).padStart(2, '0')}`
}

type LowerTab = 'timeline' | 'events' | 'history'

/**
 * Red Agent attack lab: choose a deterministic synthetic scenario, configure
 * the run, launch it, and follow its timeline as the cyber range replays it.
 */
export function RedAgentOverviewPage() {
  const playback = useSimulationPlayback()
  const workflow = useAutonomyWorkflow()
  const [summaries, setSummaries] = useState<RedScenarioSummary[]>([])
  const [definition, setDefinition] = useState<RedScenarioDefinition | null>(null)
  const [scenarioId, setScenarioId] = useState('')
  const [seed, setSeed] = useState(84)
  const [speed, setSpeed] = useState(20)
  const [modelId, setModelId] = useState('')
  const [detectionEnabled, setDetectionEnabled] = useState(true)
  const [correlationEnabled, setCorrelationEnabled] = useState(true)
  const [predictionEnabled, setPredictionEnabled] = useState(true)
  const [training, setTraining] = useState(false)
  const [trainError, setTrainError] = useState<string | null>(null)
  const [tab, setTab] = useState<LowerTab>('timeline')

  useEffect(() => {
    void listRedScenarios()
      .then(setSummaries)
      .catch(() => {
        setSummaries([])
      })
  }, [])

  const scenarios = playback.scenarios
  const defaultId =
    scenarios.find((item) => item.scenario_id === DEFAULT_SCENARIO)?.scenario_id ??
    scenarios[0]?.scenario_id ??
    ''
  const selectedId = scenarioId || defaultId
  const selected = scenarios.find((item) => item.scenario_id === selectedId) ?? null
  const summary = summaries.find((item) => item.scenario_id === selectedId) ?? null

  useEffect(() => {
    if (!selectedId) return
    let cancelled = false
    void getScenarioDefinition(selectedId)
      .then((value) => {
        if (!cancelled) setDefinition(value)
      })
      .catch(() => {
        if (!cancelled) setDefinition(null)
      })
    return () => {
      cancelled = true
    }
  }, [selectedId])

  const activeRun = playback.activeRun
  const active = playback.playbackState === 'playing' || playback.playbackState === 'paused'
  const runningThis = activeRun?.scenario_id === selectedId
  // Perturbed model identities are evaluation-only (robustness experiments)
  // and are never offered for a live run.
  const runModels = playback.models.filter(
    (item) => !('derived_from_model_id' in item.configuration_json),
  )
  const model =
    runModels.find((item) => item.model_id === modelId) ??
    runModels.find((item) => item.random_state === DEMO_MODEL_REQUEST.random_state) ??
    runModels[0] ??
    null
  const targets = useMemo(
    () =>
      selected
        ? [...new Set(selected.steps.map((step) => step.destination_id).filter(Boolean))]
        : [],
    [selected],
  )
  const canOperate = workflow.session?.can_operate ?? false

  function launch(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selected) return
    setTab('timeline')
    void playback.startSimulation({
      scenarioId: selected.scenario_id,
      seed,
      startTime: '2026-07-21T09:00',
      playbackSpeed: speed,
      detectionEnabled: detectionEnabled && model !== null,
      modelId: model?.model_id,
      correlationEnabled: detectionEnabled && correlationEnabled,
      predictionEnabled: detectionEnabled && correlationEnabled && predictionEnabled,
      topK: 3,
    })
  }

  async function trainDemoModel() {
    setTraining(true)
    setTrainError(null)
    try {
      const trained = await trainDetectionModel(DEMO_MODEL_REQUEST)
      await playback.refreshModels()
      setModelId(trained.model_id)
    } catch (reason) {
      setTrainError(toClientApiError(reason).message)
    } finally {
      setTraining(false)
    }
  }

  const progress = playback.totalEventCount
    ? playback.currentEventIndex / playback.totalEventCount
    : 0
  const runtimeErrors = [
    playback.detectionError && {
      text: playback.detectionError,
      retry: () => void playback.retryScoring(),
      label: 'Retry scoring',
      skip: playback.continueTelemetryOnly,
    },
    playback.correlationError && {
      text: playback.correlationError,
      retry: () => void playback.retryCorrelation(),
      label: 'Retry correlation',
      skip: playback.continueWithoutCorrelation,
    },
    playback.predictionError && {
      text: playback.predictionError,
      retry: () => void playback.retryPrediction(),
      label: 'Retry prediction',
      skip: playback.continueWithoutPrediction,
    },
  ].filter((item): item is Exclude<typeof item, null | '' | undefined> => Boolean(item))

  const guide: { label: string; state: 'done' | 'current' | 'todo' }[] = [
    { label: 'Choose a scenario', state: selected ? 'done' : 'current' },
    {
      label: 'Configure',
      state: activeRun ? 'done' : selected ? 'current' : 'todo',
    },
    { label: 'Launch', state: activeRun ? 'done' : 'todo' },
    {
      label: 'Observe',
      state: activeRun ? (playback.playbackState === 'completed' ? 'done' : 'current') : 'todo',
    },
  ]

  return (
    <div className="page-stack">
      <div className="cc-head">
        <div className="min-w-0">
          <h1>Red Agent lab</h1>
          <p>
            Pick a scripted, seeded attack scenario, configure it and launch it. The Red Agent
            replays synthetic telemetry against the simulated estate - never a real system.
          </p>
        </div>
      </div>

      <ol className="guide-steps" aria-label="Simulation steps">
        {guide.map((step, index) => (
          <li key={step.label} className={`is-${step.state}`}>
            <span className="guide-num" aria-hidden="true">
              {step.state === 'done' ? '✓' : index + 1}
            </span>
            {step.label}
            <span className="sr-only">
              {step.state === 'done' ? ' (done)' : step.state === 'current' ? ' (current)' : ''}
            </span>
          </li>
        ))}
      </ol>

      <div className="lab-layout">
        <section aria-label="Scenarios" className="min-w-0">
          <h2 className="lab-section-title">1 · Choose a scenario</h2>
          <div className="scenario-grid" role="radiogroup" aria-label="Synthetic scenario">
            {scenarios.map((scenario) => {
              const severity = peakSeverity(scenario)
              const isSelected = scenario.scenario_id === selectedId
              return (
                <button
                  key={scenario.scenario_id}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  disabled={active}
                  className={cn('scenario-card', isSelected && 'is-selected')}
                  onClick={() => {
                    setScenarioId(scenario.scenario_id)
                  }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3>{scenario.name.replace('Red Agent · ', '')}</h3>
                    <span className={`sev sev-${severity}`}>{severity}</span>
                  </div>
                  <p className="line-clamp-2">{scenario.description}</p>
                  <p className="scenario-foot">
                    {scenario.steps.length} steps · {clock(duration(scenario))} simulated
                    {scenario.scenario_id === DEFAULT_SCENARIO ? ' · recommended' : ''}
                  </p>
                </button>
              )
            })}
          </div>
        </section>

        <section className="panel lab-config" aria-label="Run configuration">
          <header className="panel-head">
            <h2 className="panel-title">2 · Configure and launch</h2>
          </header>
          <div className="panel-body">
            {selected ? (
              <form className="grid gap-4" onSubmit={launch}>
                <div>
                  <p className="m-0 text-[1rem] font-semibold text-[var(--text)]">
                    {selected.name}
                  </p>
                  <p className="m-0 mt-1 text-[0.88rem] text-[var(--text-dim)]">
                    {definition?.objective ?? selected.description}
                  </p>
                  <p className="m-0 mt-2 text-[0.8rem] text-[var(--text-faint)]">
                    ATT&CK: {summary?.mitre_technique_ids.join(', ') || 'none (benign baseline)'}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <label className="field">
                    <span>Seed</span>
                    <input
                      aria-label="Random seed"
                      type="number"
                      min={0}
                      value={seed}
                      disabled={active}
                      onChange={(event) => {
                        setSeed(
                          Number.isFinite(event.currentTarget.valueAsNumber)
                            ? event.currentTarget.valueAsNumber
                            : 0,
                        )
                      }}
                    />
                  </label>
                  <label className="field">
                    <span>Replay speed</span>
                    <select
                      aria-label="Playback speed"
                      value={speed}
                      disabled={active}
                      onChange={(event) => {
                        setSpeed(Number(event.target.value))
                      }}
                    >
                      {SPEEDS.map((value) => (
                        <option key={value} value={value}>
                          {value}× · {clock(Math.round(duration(selected) / value))}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                {runModels.length === 0 ? (
                  <div className="notice is-warn">
                    <CircleAlert className="size-4" />
                    <span className="grid gap-2">
                      No detection model exists yet - the replay would run without detection.
                      <span>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={training || !canOperate}
                          onClick={() => void trainDemoModel()}
                        >
                          <FlaskConical /> {training ? 'Training…' : 'Train the demo model'}
                        </Button>
                      </span>
                    </span>
                  </div>
                ) : null}
                {trainError ? (
                  <p className="m-0 text-[0.8rem] text-[var(--danger-text)]" role="alert">
                    {trainError}
                  </p>
                ) : null}
                <details className="disclosure">
                  <summary>Advanced settings</summary>
                  <div className="grid gap-4 pt-3">
                    <KeyValue
                      rows={[
                        [
                          'Initial access',
                          definition?.initial_access_point ?? selected.steps[0]?.source_id ?? '—',
                        ],
                        ['High-value objective', definition?.high_value_objective ?? '—'],
                        ['Targeted resources', targets.join(', ') || '—'],
                      ]}
                    />
                    {runModels.length > 0 ? (
                      <label className="field">
                        <span>Detection model</span>
                        <select
                          aria-label="Synthetic detection model"
                          value={model?.model_id ?? ''}
                          disabled={active}
                          onChange={(event) => {
                            setModelId(event.target.value)
                          }}
                        >
                          {runModels.map((item) => (
                            <option key={item.model_id} value={item.model_id}>
                              {item.model_type} · {item.model_id.slice(0, 8)} · rs{' '}
                              {item.random_state}
                              {item.artifact_available === false ? ' · rebuilds on use' : ''}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                    <fieldset className="grid gap-2 text-[0.88rem] text-[var(--text-dim)]">
                      <legend className="text-label mb-1">Pipeline</legend>
                      <label className="field-inline">
                        <input
                          aria-label="Enable anomaly assessment"
                          type="checkbox"
                          checked={detectionEnabled}
                          disabled={active}
                          onChange={(event) => {
                            setDetectionEnabled(event.target.checked)
                          }}
                        />
                        Anomaly detection
                      </label>
                      <label className="field-inline">
                        <input
                          aria-label="Enable correlation"
                          type="checkbox"
                          checked={correlationEnabled}
                          disabled={active || !detectionEnabled}
                          onChange={(event) => {
                            setCorrelationEnabled(event.target.checked)
                          }}
                        />
                        Incident correlation & MITRE mapping
                      </label>
                      <label className="field-inline">
                        <input
                          aria-label="Enable next-stage prediction"
                          type="checkbox"
                          checked={predictionEnabled}
                          disabled={active || !detectionEnabled || !correlationEnabled}
                          onChange={(event) => {
                            setPredictionEnabled(event.target.checked)
                          }}
                        />
                        Next-stage prediction
                      </label>
                    </fieldset>
                  </div>
                </details>
                <Button
                  type="submit"
                  size="lg"
                  disabled={playback.starting || active || !canOperate}
                  title={canOperate ? undefined : 'Launching a scenario requires the ANALYST role.'}
                >
                  <Swords /> {playback.starting ? 'Arming scenario…' : 'Launch scenario'}
                </Button>
                {DEMO_MODE ? (
                  <p className="m-0 text-[0.8rem] text-[var(--text-faint)]">
                    Demo mode: deterministic seed 84 and the staged compromise are preselected.
                  </p>
                ) : null}
              </form>
            ) : (
              <p className="m-0 text-[0.88rem] text-[var(--text-faint)]">
                {playback.loadingScenarios ? 'Loading scenarios…' : 'No scenario available.'}
              </p>
            )}
          </div>
        </section>
      </div>

      <section className="panel" aria-label="Observe">
        <header className="panel-head">
          <div className="min-w-0">
            <h2 className="panel-title">4 · Observe</h2>
            <p className="panel-subtitle">
              {activeRun
                ? `${scenarios.find((item) => item.scenario_id === activeRun.scenario_id)?.name ?? activeRun.scenario_id} · seed ${String(activeRun.seed)} · ${playback.playbackState}`
                : 'Launch a scenario to stream it here. Until then, preview the selected scenario.'}
            </p>
          </div>
          {activeRun ? (
            <div className="btn-row">
              <Button asChild size="sm" variant="outline">
                <Link to="/">Command Centre</Link>
              </Button>
              <Button asChild size="sm" variant="outline">
                <Link to="/digital-twin">Digital Twin</Link>
              </Button>
            </div>
          ) : null}
        </header>
        <div className="panel-body grid gap-4">
          {activeRun ? (
            <div className="grid gap-3">
              <div className="flex items-center gap-3">
                <Bar
                  value={progress}
                  tone={playback.playbackState === 'playing' ? 'danger' : 'ok'}
                  label="Replay progress"
                />
                <span className="mono whitespace-nowrap text-[0.85rem] text-[var(--text-dim)]">
                  {playback.currentEventIndex}/{playback.totalEventCount}
                </span>
              </div>
              <div className="btn-row">
                {playback.playbackState === 'playing' ? (
                  <Button size="sm" variant="outline" onClick={playback.pause}>
                    <Pause /> Pause
                  </Button>
                ) : null}
                {playback.playbackState === 'paused' ? (
                  <Button size="sm" variant="outline" onClick={playback.resume}>
                    <Play /> Resume
                  </Button>
                ) : null}
                <Button size="sm" variant="outline" onClick={playback.stop} disabled={!active}>
                  <Square /> Stop
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={playback.resetView}
                  disabled={active || !activeRun}
                >
                  <RotateCcw /> Reset view
                </Button>
              </div>
            </div>
          ) : null}
          {playback.error ? (
            <p className="m-0 text-[0.85rem] text-[var(--danger-text)]" role="alert">
              {playback.error}{' '}
              {activeRun ? (
                <button className="card-link" onClick={playback.retry}>
                  Retry connection
                </button>
              ) : null}
            </p>
          ) : null}
          {runtimeErrors.map((item) => (
            <div key={item.label} className="error-state" role="alert">
              <span className="flex-1">{item.text}</span>
              <Button size="sm" variant="outline" onClick={item.retry}>
                {item.label}
              </Button>
              <Button size="sm" variant="ghost" onClick={item.skip}>
                Continue without
              </Button>
            </div>
          ))}
          <div className="line-tabs is-page" role="tablist" aria-label="Red Agent views">
            {(
              [
                ['timeline', 'Scenario timeline'],
                ['events', 'Event stream'],
                ['history', 'Run history'],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={tab === id}
                className="line-tab"
                onClick={() => {
                  setTab(id)
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="lab-tab-body">
            {tab === 'timeline' && selected ? (
              <ol className="step-timeline" aria-label="Scenario steps">
                {selected.steps.map((step) => {
                  const played = runningThis && step.sequence <= playback.currentEventIndex
                  const current = runningThis && step.sequence === playback.currentEventIndex
                  const technique = summary?.step_techniques.find(
                    (item) => item.step_sequence === step.sequence,
                  )
                  return (
                    <li
                      key={step.sequence}
                      className={cn(current ? 'is-current' : played && 'is-played')}
                    >
                      <span className="step-time">+{clock(step.offset_seconds)}</span>
                      <span className="step-dot" aria-hidden="true" />
                      <span className="step-text">
                        {step.description}
                        <span className="block text-[0.8rem] text-[var(--text-faint)]">
                          {step.source_id} → {step.destination_id ?? '—'} · {step.severity}
                          {technique?.technique_id ? (
                            <span className="mono text-[var(--danger-text)]">
                              {' '}
                              · {technique.technique_id}
                            </span>
                          ) : null}
                        </span>
                      </span>
                    </li>
                  )
                })}
              </ol>
            ) : null}
            {tab === 'events' ? <LiveEventStream expanded /> : null}
            {tab === 'history' ? <RunHistory /> : null}
          </div>
        </div>
      </section>
    </div>
  )
}
