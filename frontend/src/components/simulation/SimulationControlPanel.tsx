import { Pause, Play, RefreshCw, RotateCcw, Square, Wifi, WifiOff } from 'lucide-react'
import { useState, type SyntheticEvent } from 'react'

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
  } = useSimulationPlayback()
  const [scenarioId, setScenarioId] = useState('')
  const [seed, setSeed] = useState(42)
  const [startTime, setStartTime] = useState('2026-07-21T09:00')
  const [playbackSpeed, setPlaybackSpeed] = useState(10)

  const selectedScenarioId = scenarioId || scenarios[0]?.scenario_id || ''

  function submit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedScenarioId) return
    void startSimulation({ scenarioId: selectedScenarioId, seed, startTime, playbackSpeed })
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
          <Button type="submit" disabled={!selectedScenarioId || starting || active}>
            <Play className="size-4" />
            {starting ? 'Starting…' : 'Start Synthetic Simulation'}
          </Button>
        </form>

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
