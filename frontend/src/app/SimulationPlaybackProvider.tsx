import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { SimulationPlaybackContext, type StartSimulationInput } from './simulationPlaybackContext'
import { toClientApiError } from '../services/apiClient'
import { PlaybackWebSocketClient } from '../services/playbackWebSocketClient'
import { createSimulationRun, getScenarios, getSimulationRuns } from '../services/simulationApi'
import { getSnapshotPayload, getTelemetryPayload, type PlaybackEnvelope } from '../types/playback'
import type {
  PlaybackState,
  SimulationRun,
  SimulationScenario,
  TelemetryEvent,
} from '../types/simulation'
import type { WebSocketConnectionState } from '../types/websocket'

const MAX_RENDERED_EVENTS = 200

export function SimulationPlaybackProvider({ children }: { children: ReactNode }) {
  const [scenarios, setScenarios] = useState<SimulationScenario[]>([])
  const [runs, setRuns] = useState<SimulationRun[]>([])
  const [activeRun, setActiveRun] = useState<SimulationRun | null>(null)
  const [events, setEvents] = useState<TelemetryEvent[]>([])
  const [playbackState, setPlaybackState] = useState<PlaybackState>('idle')
  const [connectionState, setConnectionState] = useState<WebSocketConnectionState>('disconnected')
  const [currentEventIndex, setCurrentEventIndex] = useState(0)
  const [totalEventCount, setTotalEventCount] = useState(0)
  const [loadingScenarios, setLoadingScenarios] = useState(true)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const clientRef = useRef<PlaybackWebSocketClient | null>(null)

  useEffect(() => {
    let active = true
    void Promise.all([getScenarios(), getSimulationRuns()])
      .then(([scenarioData, runData]) => {
        if (!active) return
        setScenarios(scenarioData)
        setRuns(runData)
      })
      .catch((reason: unknown) => {
        if (active) setError(toClientApiError(reason).message)
      })
      .finally(() => {
        if (active) setLoadingScenarios(false)
      })
    return () => {
      active = false
      clientRef.current?.disconnect()
    }
  }, [])

  const handleMessage = useCallback((message: PlaybackEnvelope) => {
    setError(null)
    if (message.message_type === 'connection_ack') {
      clientRef.current?.sendControl('start')
      return
    }
    const snapshot = getSnapshotPayload(message)
    if (snapshot) {
      setTotalEventCount(snapshot.total_event_count)
      setCurrentEventIndex(snapshot.starting_after_sequence)
      return
    }
    const telemetry = getTelemetryPayload(message)
    if (telemetry) {
      setEvents((current) => [...current, telemetry.event].slice(-MAX_RENDERED_EVENTS))
      setCurrentEventIndex(telemetry.event_index)
      setTotalEventCount(telemetry.total_event_count)
      return
    }
    const stateByMessage: Partial<Record<PlaybackEnvelope['message_type'], PlaybackState>> = {
      playback_started: 'playing',
      playback_paused: 'paused',
      playback_resumed: 'playing',
      playback_stopped: 'stopped',
      playback_completed: 'completed',
      error: 'error',
    }
    const nextState = stateByMessage[message.message_type]
    if (nextState) setPlaybackState(nextState)
    if (message.message_type === 'error') {
      const detail = message.payload.message
      setError(typeof detail === 'string' ? detail : 'Synthetic playback reported an error.')
    }
    if (
      message.message_type === 'playback_stopped' ||
      message.message_type === 'playback_completed'
    ) {
      clientRef.current?.disconnect()
    }
  }, [])

  const openRun = useCallback(
    (run: SimulationRun, afterSequence: number) => {
      clientRef.current?.disconnect()
      setActiveRun(run)
      setError(null)
      setPlaybackState('idle')
      setConnectionState('disconnected')
      const client = new PlaybackWebSocketClient({
        onConnectionState: setConnectionState,
        onMessage: handleMessage,
        onProtocolError: setError,
      })
      clientRef.current = client
      client.connect(run.simulation_run_id, afterSequence)
    },
    [handleMessage],
  )

  const startSimulation = useCallback(
    async (input: StartSimulationInput) => {
      setStarting(true)
      setError(null)
      setEvents([])
      setCurrentEventIndex(0)
      try {
        const startTime = input.startTime.endsWith('Z') ? input.startTime : `${input.startTime}:00Z`
        const run = await createSimulationRun({
          scenario_id: input.scenarioId,
          seed: input.seed,
          start_time: startTime,
          playback_speed: input.playbackSpeed,
        })
        setTotalEventCount(run.event_count)
        setRuns((current) => [
          run,
          ...current.filter((item) => item.simulation_run_id !== run.simulation_run_id),
        ])
        openRun(run, 0)
      } catch (reason) {
        setError(toClientApiError(reason).message)
        setConnectionState('error')
      } finally {
        setStarting(false)
      }
    },
    [openRun],
  )

  const replayRun = useCallback(
    (run: SimulationRun) => {
      setEvents([])
      setCurrentEventIndex(0)
      setTotalEventCount(run.event_count)
      openRun(run, 0)
    },
    [openRun],
  )

  const pause = useCallback(() => {
    clientRef.current?.sendControl('pause')
  }, [])
  const resume = useCallback(() => {
    clientRef.current?.sendControl('resume')
  }, [])
  const stop = useCallback(() => {
    clientRef.current?.sendControl('stop')
  }, [])
  const resetView = useCallback(() => {
    setEvents([])
    setCurrentEventIndex(0)
    setError(null)
  }, [])
  const retry = useCallback(() => {
    if (activeRun) openRun(activeRun, currentEventIndex)
  }, [activeRun, currentEventIndex, openRun])

  const simulatedElapsedSeconds = useMemo(() => {
    const latest = events.at(-1)
    if (!activeRun || !latest) return 0
    return Math.max(0, (Date.parse(latest.timestamp) - Date.parse(activeRun.start_time)) / 1000)
  }, [activeRun, events])

  const value = useMemo(
    () => ({
      scenarios,
      runs,
      activeRun,
      events,
      playbackState,
      connectionState,
      currentEventIndex,
      totalEventCount,
      simulatedElapsedSeconds,
      loadingScenarios,
      starting,
      error,
      startSimulation,
      replayRun,
      pause,
      resume,
      stop,
      resetView,
      retry,
    }),
    [
      scenarios,
      runs,
      activeRun,
      events,
      playbackState,
      connectionState,
      currentEventIndex,
      totalEventCount,
      simulatedElapsedSeconds,
      loadingScenarios,
      starting,
      error,
      startSimulation,
      replayRun,
      pause,
      resume,
      stop,
      resetView,
      retry,
    ],
  )
  return (
    <SimulationPlaybackContext.Provider value={value}>
      {children}
    </SimulationPlaybackContext.Provider>
  )
}
