import { Pause, Play, RefreshCw, RotateCcw, Square, Wifi, WifiOff } from 'lucide-react'
import { useState, type SyntheticEvent } from 'react'
import { Link } from 'react-router-dom'

import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { Button } from '../ui/button'
import { Card, CardContent, CardHeader } from '../ui/card'

export function SimulationControlPanel() {
  const {
    scenarios,
    activeRun,
    playbackState,
    connectionState,
    currentEventIndex,
    totalEventCount,
    simulatedElapsedSeconds,
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
    scoringStatus,
    detectionError,
    retryScoring,
    continueTelemetryOnly,
    correlationStatus,
    correlationError,
    retryCorrelation,
    continueWithoutCorrelation,
    predictionStatus,
    predictionError,
    retryPrediction,
    continueWithoutPrediction,
  } = useSimulationPlayback()
  const [scenarioId, setScenarioId] = useState('')
  const [seed, setSeed] = useState(42)
  const [startTime, setStartTime] = useState('2026-07-21T09:00')
  const [playbackSpeed, setPlaybackSpeed] = useState(10)
  const [detectionEnabled, setDetectionEnabled] = useState(false)
  const [modelId, setModelId] = useState('')
  const [correlationEnabled, setCorrelationEnabled] = useState(false)
  const [predictionEnabled, setPredictionEnabled] = useState(false)
  const [topK, setTopK] = useState(3)

  const selectedScenarioId = scenarioId || scenarios[0]?.scenario_id || ''

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

  const connected = connectionState === 'connected'
  const active = playbackState === 'playing' || playbackState === 'paused'
  return (
    <Card className="xl:col-span-2">
      <CardHeader>
        <div>
          <p className="eyebrow">Synthetic simulation controls</p>
          <h2 className="panel-title">Deterministic telemetry playback</h2>
        </div>
        <span className={connected ? 'status-chip is-healthy' : 'status-chip is-offline'}>
          {connected ? <Wifi className="size-3.5" /> : <WifiOff className="size-3.5" />}
          {connectionState}
        </span>
      </CardHeader>
      <CardContent>
        <form className="simulation-form" onSubmit={submit}>
          <label>
            <span>Scenario</span>
            <select
              aria-label="Synthetic scenario"
              value={selectedScenarioId}
              onChange={(event) => {
                setScenarioId(event.target.value)
              }}
              disabled={loadingScenarios || active}
            >
              <option value="">
                {loadingScenarios ? 'Loading scenarios…' : 'Select scenario'}
              </option>
              {scenarios.map((scenario) => (
                <option key={scenario.scenario_id} value={scenario.scenario_id}>
                  {scenario.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex-row items-center self-center">
            <input
              aria-label="Enable anomaly assessment"
              type="checkbox"
              checked={detectionEnabled}
              onChange={(event) => {
                setDetectionEnabled(event.target.checked)
              }}
              disabled={active}
            />
            <span>Enable anomaly assessment</span>
          </label>
          {detectionEnabled ? (
            <label>
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
            <label className="flex-row items-center self-center">
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
              <span>Enable correlation</span>
            </label>
          ) : null}
          {correlationEnabled ? (
            <label className="flex-row items-center self-center">
              <input
                aria-label="Enable next-stage prediction"
                type="checkbox"
                checked={predictionEnabled}
                onChange={(event) => {
                  setPredictionEnabled(event.target.checked)
                }}
                disabled={active}
              />
              <span>Enable next-stage prediction</span>
            </label>
          ) : null}
          {predictionEnabled ? (
            <label>
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
          <label>
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
          <label>
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
          <label>
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
          <Button
            type="submit"
            disabled={
              !selectedScenarioId || starting || active || (detectionEnabled && models.length === 0)
            }
          >
            <Play className="size-4" />
            {starting ? 'Starting…' : 'Start Synthetic Simulation'}
          </Button>
        </form>
        {detectionEnabled && models.length === 0 && !modelsLoading ? (
          <p className="mt-3 text-sm text-amber-300">
            No synthetic detection model is available.{' '}
            <Link className="underline" to="/model-analytics">
              Create a synthetic demo model
            </Link>
          </p>
        ) : null}
        {detectionEnabled && models.length > 0
          ? (() => {
              const model = models.find(
                (item) => item.model_id === (modelId || models[0]?.model_id),
              )
              return model ? (
                <p className="mt-3 text-xs text-slate-400">
                  Schema: {model.feature_schema_version} · Calibration: {model.calibration_method} ·
                  Detector: {model.model_type}
                </p>
              ) : null
            })()
          : null}
        <p className="mt-2 text-xs text-slate-500" aria-live="polite">
          Scoring state: {scoringStatus}
        </p>
        <p className="mt-1 text-xs text-slate-500" aria-live="polite">
          Correlation preparation: {correlationStatus}
        </p>
        <p className="mt-1 text-xs text-slate-500" aria-live="polite">
          Prediction preparation: {predictionStatus}
        </p>
        {predictionError ? (
          <div className="mt-3 flex flex-wrap items-center gap-2" role="alert">
            <span className="text-sm text-red-200">{predictionError}</span>
            <Button size="sm" variant="outline" onClick={() => void retryPrediction()}>
              Analyze Predictions
            </Button>
            <Button size="sm" variant="outline" onClick={continueWithoutPrediction}>
              Continue Without Prediction
            </Button>
          </div>
        ) : null}
        {correlationError ? (
          <div className="mt-3 flex flex-wrap items-center gap-2" role="alert">
            <span className="text-sm text-red-200">{correlationError}</span>
            <Button size="sm" variant="outline" onClick={() => void retryCorrelation()}>
              Analyze Synthetic Run
            </Button>
            <Button size="sm" variant="outline" onClick={continueWithoutCorrelation}>
              Continue Without Correlation
            </Button>
          </div>
        ) : null}
        {detectionError ? (
          <div className="mt-3 flex flex-wrap items-center gap-2" role="alert">
            <span className="text-sm text-red-200">{detectionError}</span>
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
          </div>
        ) : null}

        <div className="playback-controls" aria-label="Playback controls">
          <Button
            variant="outline"
            size="sm"
            onClick={pause}
            disabled={playbackState !== 'playing'}
          >
            <Pause className="size-4" />
            Pause
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={resume}
            disabled={playbackState !== 'paused'}
          >
            <Play className="size-4" />
            Resume
          </Button>
          <Button variant="outline" size="sm" onClick={stop} disabled={!active}>
            <Square className="size-4" />
            Stop
          </Button>
          <Button variant="ghost" size="sm" onClick={resetView} disabled={active}>
            <RotateCcw className="size-4" />
            Reset View
          </Button>
          {error && activeRun ? (
            <Button variant="outline" size="sm" onClick={retry}>
              <RefreshCw className="size-4" />
              Retry connection
            </Button>
          ) : null}
        </div>

        <div className="playback-facts" aria-live="polite">
          <div>
            <span>Playback state</span>
            <strong>{playbackState}</strong>
          </div>
          <div>
            <span>Event position</span>
            <strong>
              {currentEventIndex} / {totalEventCount}
            </strong>
          </div>
          <div>
            <span>Simulated elapsed</span>
            <strong>{simulatedElapsedSeconds}s</strong>
          </div>
          <div>
            <span>Active synthetic run</span>
            <strong className="technical">
              {activeRun?.simulation_run_id.slice(0, 8) ?? 'none'}
            </strong>
          </div>
        </div>
        {error ? (
          <p className="mt-4 text-sm text-red-300" role="alert">
            {error}
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}
