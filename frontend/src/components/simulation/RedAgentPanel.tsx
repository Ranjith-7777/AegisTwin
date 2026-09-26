import { Bot, Pause, Play, RotateCcw, Swords } from 'lucide-react'
import { useState, type SyntheticEvent } from 'react'
import { Link } from 'react-router-dom'

import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { DEMO_MODE } from '../../lib/constants'
import type { CommandCentreState } from '../../lib/commandCentre'
import { Button } from '../ui/button'

/**
 * Compact Overview control rail. Advanced run inputs stay available inside the
 * disclosure so no simulation capability is lost.
 */
export function RedAgentPanel({ state }: { state: CommandCentreState }) {
  const {
    scenarios,
    activeRun,
    playbackState,
    currentEventIndex,
    totalEventCount,
    loadingScenarios,
    starting,
    error,
    startSimulation,
    pause,
    resume,
    stop,
    resetView,
    retry,
    models,
    modelsLoading,
    detectionError,
    retryScoring,
    continueTelemetryOnly,
    correlationError,
    retryCorrelation,
    continueWithoutCorrelation,
    predictionError,
    retryPrediction,
    continueWithoutPrediction,
  } = useSimulationPlayback()
  const [scenarioId, setScenarioId] = useState(DEMO_MODE ? 'staged-compromise-demo' : '')
  const [seed, setSeed] = useState(DEMO_MODE ? 84 : 42)
  const [startTime, setStartTime] = useState('2026-07-21T09:00')
  const [playbackSpeed, setPlaybackSpeed] = useState(DEMO_MODE ? 50 : 10)
  const [detectionEnabled, setDetectionEnabled] = useState(true)
  const [modelId, setModelId] = useState('')
  const [correlationEnabled, setCorrelationEnabled] = useState(true)
  const [predictionEnabled, setPredictionEnabled] = useState(true)
  const [topK, setTopK] = useState(3)

  const selectedScenarioId = scenarioId || scenarios[0]?.scenario_id || ''
  const scenario = scenarios.find((item) => item.scenario_id === selectedScenarioId) ?? null
  const active = playbackState === 'playing' || playbackState === 'paused'

  function submit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedScenarioId) return
    void startSimulation({
      scenarioId: selectedScenarioId,
      seed,
      startTime,
      playbackSpeed,
      detectionEnabled,
      modelId: detectionEnabled ? modelId || models[0]?.model_id : undefined,
      correlationEnabled,
      predictionEnabled,
      topK,
    })
  }

  return (
    <section className="card rail" aria-label="Red Agent controls">
      <div className="card-head">
        <h2 className="card-title">Red Agent</h2>
        <span className={`chip chip-${state.redAgentState === 'active' ? 'danger' : 'muted'}`}>
          {state.redAgentState}
        </span>
      </div>
      <form className="rail-body" onSubmit={submit}>
        <label className="field">
          <span>Scenario</span>
          <select
            aria-label="Synthetic scenario"
            value={selectedScenarioId}
            onChange={(event) => {
              setScenarioId(event.target.value)
            }}
            disabled={loadingScenarios || active}
          >
            <option value="">{loadingScenarios ? 'Loading scenarios…' : 'Select scenario'}</option>
            {scenarios.map((item) => (
              <option key={item.scenario_id} value={item.scenario_id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <p className="rail-description">
          {scenario?.description ?? 'Select a deterministic Red Agent scenario to arm the range.'}
        </p>
        <div className="rail-actions">
          <Button
            type="submit"
            size="sm"
            disabled={
              !selectedScenarioId || starting || active || (detectionEnabled && models.length === 0)
            }
          >
            <Play className="size-4" />
            {starting ? 'Starting…' : 'Start'}
          </Button>
          {playbackState === 'playing' ? (
            <Button type="button" variant="outline" size="sm" onClick={pause}>
              <Pause className="size-4" />
              Pause
            </Button>
          ) : null}
          {playbackState === 'paused' ? (
            <Button type="button" variant="outline" size="sm" onClick={resume}>
              <Play className="size-4" />
              Resume
            </Button>
          ) : null}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              if (active) stop()
              resetView()
            }}
            disabled={!activeRun && playbackState === 'idle'}
          >
            <RotateCcw className="size-4" />
            Reset
          </Button>
        </div>
        {detectionEnabled && models.length === 0 && !modelsLoading ? (
          <p className="rail-note is-warn">
            No detection model available.{' '}
            <Link to="/model-analytics">Create one in Detection Models</Link>
          </p>
        ) : null}
        <details className="rail-advanced">
          <summary>Advanced run options</summary>
          <div className="rail-grid">
            <label className="field field-inline">
              <input
                aria-label="Enable anomaly assessment"
                type="checkbox"
                checked={detectionEnabled}
                onChange={(event) => {
                  setDetectionEnabled(event.target.checked)
                }}
                disabled={active}
              />
              <span>Anomaly assessment</span>
            </label>
            {detectionEnabled ? (
              <label className="field">
                <span>Detection model</span>
                <select
                  aria-label="Synthetic detection model"
                  value={modelId || models[0]?.model_id || ''}
                  onChange={(event) => {
                    setModelId(event.target.value)
                  }}
                  disabled={modelsLoading || active}
                >
                  {models.length === 0 ? <option value="">No model available</option> : null}
                  {models.map((model) => (
                    <option key={model.model_id} value={model.model_id}>
                      {model.model_id.slice(0, 8)} · {model.feature_schema_version}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {detectionEnabled ? (
              <label className="field field-inline">
                <input
                  aria-label="Enable correlation"
                  type="checkbox"
                  checked={correlationEnabled}
                  onChange={(event) => {
                    setCorrelationEnabled(event.target.checked)
                    if (!event.target.checked) setPredictionEnabled(false)
                  }}
                  disabled={active}
                />
                <span>Correlation</span>
              </label>
            ) : null}
            {correlationEnabled ? (
              <label className="field field-inline">
                <input
                  aria-label="Enable next-stage prediction"
                  type="checkbox"
                  checked={predictionEnabled}
                  onChange={(event) => {
                    setPredictionEnabled(event.target.checked)
                  }}
                  disabled={active}
                />
                <span>Next-stage prediction</span>
              </label>
            ) : null}
            {predictionEnabled ? (
              <label className="field">
                <span>Ranked hypotheses</span>
                <select
                  aria-label="Prediction top K"
                  value={topK}
                  onChange={(event) => {
                    setTopK(Number(event.target.value))
                  }}
                  disabled={active}
                >
                  {[1, 2, 3, 4, 5].map((value) => (
                    <option key={value} value={value}>
                      Top {value}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <label className="field">
              <span>Seed</span>
              <input
                aria-label="Random seed"
                type="number"
                min="0"
                value={seed}
                onChange={(event) => {
                  setSeed(event.currentTarget.valueAsNumber)
                }}
                disabled={active}
              />
            </label>
            <label className="field">
              <span>UTC start time</span>
              <input
                aria-label="UTC start time"
                type="datetime-local"
                value={startTime}
                onChange={(event) => {
                  setStartTime(event.target.value)
                }}
                disabled={active}
              />
            </label>
            <label className="field">
              <span>Playback speed</span>
              <select
                aria-label="Playback speed"
                value={playbackSpeed}
                onChange={(event) => {
                  setPlaybackSpeed(Number(event.target.value))
                }}
                disabled={active}
              >
                {[1, 2, 10, 50].map((speed) => (
                  <option key={speed} value={speed}>
                    {speed}×
                  </option>
                ))}
              </select>
            </label>
          </div>
        </details>
      </form>
      <div className="agent-list">
        <div className="agent-row">
          <span className="agent-icon tone-danger">
            <Swords className="size-4" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="agent-name">Red Agent</p>
            <p className="agent-detail">{state.redAgentDetail}</p>
          </div>
          <span className="agent-count">
            {currentEventIndex}/{totalEventCount}
          </span>
        </div>
        <div className="agent-row">
          <span className="agent-icon tone-info">
            <Bot className="size-4" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="agent-name">Blue Agent</p>
            <p className="agent-detail">{state.blueAgentDetail}</p>
          </div>
          <span className={`chip chip-${state.blueAgentState === 'active' ? 'healthy' : 'muted'}`}>
            {state.blueAgentState}
          </span>
        </div>
      </div>
      {(detectionError ?? correlationError ?? predictionError ?? error) ? (
        <div className="rail-errors" role="alert">
          {detectionError ? (
            <p>
              {detectionError}
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  void retryScoring()
                }}
              >
                Retry Scoring
              </Button>
              <Button size="sm" variant="outline" onClick={continueTelemetryOnly}>
                Continue Telemetry Only
              </Button>
            </p>
          ) : null}
          {correlationError ? (
            <p>
              {correlationError}
              <Button size="sm" variant="outline" onClick={() => void retryCorrelation()}>
                Analyze Synthetic Run
              </Button>
              <Button size="sm" variant="outline" onClick={continueWithoutCorrelation}>
                Continue Without Correlation
              </Button>
            </p>
          ) : null}
          {predictionError ? (
            <p>
              {predictionError}
              <Button size="sm" variant="outline" onClick={() => void retryPrediction()}>
                Analyze Predictions
              </Button>
              <Button size="sm" variant="outline" onClick={continueWithoutPrediction}>
                Continue Without Prediction
              </Button>
            </p>
          ) : null}
          {error ? (
            <p>
              {error}
              {activeRun ? (
                <Button size="sm" variant="outline" onClick={retry}>
                  Retry connection
                </Button>
              ) : null}
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
