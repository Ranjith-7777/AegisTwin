import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { SimulationPlaybackContext, type StartSimulationInput } from './simulationPlaybackContext'
import { toClientApiError } from '../services/apiClient'
import { PlaybackWebSocketClient } from '../services/playbackWebSocketClient'
import { createSimulationRun, getScenarios, getSimulationRuns } from '../services/simulationApi'
import {
  getAssessmentPayload,
  getIncidentPayload,
  getSnapshotPayload,
  getTelemetryPayload,
  getTechniquePayload,
  type PlaybackEnvelope,
} from '../types/playback'
import { getDetectionModels, scoreSimulationRun } from '../services/detectionApi'
import { analyzeRun } from '../services/correlationApi'
import type { IncidentCandidate, TechniqueObservation } from '../types/correlation'
import type { AnomalyAssessment, DetectionModel, ScoringStatus } from '../types/detection'
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
  const [models, setModels] = useState<DetectionModel[]>([])
  const [modelsLoading, setModelsLoading] = useState(true)
  const [detectionEnabled, setDetectionEnabled] = useState(false)
  const [selectedModel, setSelectedModel] = useState<DetectionModel | null>(null)
  const [scoringStatus, setScoringStatus] = useState<ScoringStatus>('idle')
  const [detectionError, setDetectionError] = useState<string | null>(null)
  const [assessmentsByEventId, setAssessmentsByEventId] = useState<
    Record<string, AnomalyAssessment>
  >({})
  const [assessmentTimeline, setAssessmentTimeline] = useState<AnomalyAssessment[]>([])
  const [correlationEnabled, setCorrelationEnabled] = useState(false)
  const [correlationStatus, setCorrelationStatus] = useState<
    'idle' | 'analyzing' | 'ready' | 'error'
  >('idle')
  const [correlationError, setCorrelationError] = useState<string | null>(null)
  const [techniqueTimeline, setTechniqueTimeline] = useState<TechniqueObservation[]>([])
  const [currentIncidentCandidate, setCurrentIncidentCandidate] =
    useState<IncidentCandidate | null>(null)
  const pendingRunRef = useRef<SimulationRun | null>(null)
  const detectionStartRef = useRef<{
    enabled: boolean
    modelId?: string
    correlationEnabled?: boolean
  }>({ enabled: false })
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
    void getDetectionModels()
      .then((modelData) => {
        if (active) setModels(modelData.filter((model) => model.synthetic))
      })
      .catch(() => {
        if (active) setModels([])
      })
      .finally(() => {
        if (active) setModelsLoading(false)
      })
    return () => {
      active = false
      clientRef.current?.disconnect()
    }
  }, [])

  const handleMessage = useCallback(
    (message: PlaybackEnvelope) => {
      setError(null)
      if (message.message_type === 'connection_ack') {
        clientRef.current?.sendControl('start', undefined, {
          detectionEnabled: detectionStartRef.current.enabled,
          modelId: detectionStartRef.current.modelId,
          correlationEnabled: detectionStartRef.current.correlationEnabled,
        })
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
      const assessment = getAssessmentPayload(message)
      if (assessment) {
        if (
          message.run_id !== pendingRunRef.current?.simulation_run_id &&
          message.run_id !== activeRun?.simulation_run_id
        )
          return
        setAssessmentsByEventId((current) => ({ ...current, [assessment.event_id]: assessment }))
        setAssessmentTimeline((current) =>
          current.some((item) => item.assessment_id === assessment.assessment_id)
            ? current
            : [...current, assessment],
        )
        return
      }
      const technique = getTechniquePayload(message)
      if (technique) {
        setTechniqueTimeline((current) =>
          current.some((item) => item.mapping_id === technique.mapping_id)
            ? current
            : [...current, technique],
        )
        return
      }
      const candidate = getIncidentPayload(message)
      if (candidate) {
        setCurrentIncidentCandidate(candidate)
        return
      }
      if (message.message_type === 'correlation_ready') setCorrelationStatus('ready')
      if (
        message.message_type === 'correlation_error' ||
        message.message_type === 'correlation_warning'
      ) {
        setCorrelationStatus('error')
        setCorrelationError(
          typeof message.payload.message === 'string'
            ? message.payload.message
            : 'Synthetic correlation is unavailable.',
        )
      }
      if (message.message_type === 'detection_ready') setScoringStatus('ready')
      if (
        message.message_type === 'detection_error' ||
        message.message_type === 'detection_warning'
      ) {
        const detail = message.payload.message
        setDetectionError(
          typeof detail === 'string' ? detail : 'Synthetic assessment is unavailable.',
        )
        setScoringStatus('error')
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
    },
    [activeRun?.simulation_run_id],
  )

  const openRun = useCallback(
    (run: SimulationRun, afterSequence: number, detection = detectionStartRef.current) => {
      clientRef.current?.disconnect()
      setActiveRun(run)
      setError(null)
      setPlaybackState('idle')
      detectionStartRef.current = detection
      pendingRunRef.current = run
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
      setAssessmentsByEventId({})
      setAssessmentTimeline([])
      setTechniqueTimeline([])
      setCurrentIncidentCandidate(null)
      setCorrelationError(null)
      setDetectionError(null)
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
        const model = input.detectionEnabled
          ? (models.find((item) => item.model_id === input.modelId) ?? null)
          : null
        setDetectionEnabled(input.detectionEnabled)
        setCorrelationEnabled(input.correlationEnabled)
        setSelectedModel(model)
        pendingRunRef.current = run
        if (input.detectionEnabled && model) {
          setScoringStatus('scoring')
          try {
            const result = await scoreSimulationRun(run.simulation_run_id, model.model_id)
            if (result.assessment_count !== run.event_count) {
              throw new Error('Persisted assessment count does not match the run event count.')
            }
            setScoringStatus('ready')
            if (input.correlationEnabled) {
              setCorrelationStatus('analyzing')
              await analyzeRun(run.simulation_run_id, model.model_id)
              setCorrelationStatus('ready')
            } else {
              setCorrelationStatus('idle')
            }
            openRun(run, 0, {
              enabled: true,
              modelId: model.model_id,
              correlationEnabled: input.correlationEnabled,
            })
          } catch (reason) {
            setScoringStatus('error')
            setDetectionError(
              reason instanceof Error ? reason.message : toClientApiError(reason).message,
            )
            setActiveRun(run)
          }
        } else {
          setScoringStatus('idle')
          openRun(run, 0, { enabled: false })
        }
      } catch (reason) {
        setError(toClientApiError(reason).message)
        setConnectionState('error')
      } finally {
        setStarting(false)
      }
    },
    [models, openRun],
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
  const retryScoring = useCallback(async () => {
    const run = pendingRunRef.current
    if (!run || !selectedModel) return
    setScoringStatus('scoring')
    setDetectionError(null)
    try {
      const result = await scoreSimulationRun(run.simulation_run_id, selectedModel.model_id, true)
      if (result.assessment_count !== run.event_count)
        throw new Error('Persisted assessment count does not match the run event count.')
      setScoringStatus('ready')
      openRun(run, 0, { enabled: true, modelId: selectedModel.model_id })
    } catch (reason) {
      setScoringStatus('error')
      setDetectionError(reason instanceof Error ? reason.message : toClientApiError(reason).message)
    }
  }, [openRun, selectedModel])
  const continueTelemetryOnly = useCallback(() => {
    const run = pendingRunRef.current
    if (!run) return
    setDetectionEnabled(false)
    setSelectedModel(null)
    setDetectionError(null)
    setScoringStatus('idle')
    openRun(run, 0, { enabled: false })
  }, [openRun])
  const retryCorrelation = useCallback(async () => {
    const run = pendingRunRef.current
    if (!run || !selectedModel) return
    setCorrelationStatus('analyzing')
    setCorrelationError(null)
    try {
      await analyzeRun(run.simulation_run_id, selectedModel.model_id, true)
      setCorrelationStatus('ready')
      openRun(run, 0, {
        enabled: true,
        modelId: selectedModel.model_id,
        correlationEnabled: true,
      })
    } catch (reason) {
      setCorrelationStatus('error')
      setCorrelationError(toClientApiError(reason).message)
    }
  }, [openRun, selectedModel])
  const continueWithoutCorrelation = useCallback(() => {
    const run = pendingRunRef.current
    if (!run || !selectedModel) return
    setCorrelationEnabled(false)
    setCorrelationStatus('idle')
    setCorrelationError(null)
    openRun(run, 0, { enabled: true, modelId: selectedModel.model_id })
  }, [openRun, selectedModel])
  const refreshModels = useCallback(async () => {
    setModelsLoading(true)
    try {
      setModels((await getDetectionModels()).filter((model) => model.synthetic))
    } finally {
      setModelsLoading(false)
    }
  }, [])

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
      detectionEnabled,
      selectedModel,
      models,
      modelsLoading,
      scoringStatus,
      detectionError,
      assessmentsByEventId,
      assessmentTimeline,
      currentAssessment: assessmentTimeline.at(-1) ?? null,
      correlationEnabled,
      correlationStatus,
      correlationError,
      techniqueTimeline,
      currentIncidentCandidate,
      startSimulation,
      replayRun,
      pause,
      resume,
      stop,
      resetView,
      retry,
      retryScoring,
      continueTelemetryOnly,
      refreshModels,
      retryCorrelation,
      continueWithoutCorrelation,
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
      detectionEnabled,
      selectedModel,
      models,
      modelsLoading,
      scoringStatus,
      detectionError,
      assessmentsByEventId,
      assessmentTimeline,
      correlationEnabled,
      correlationStatus,
      correlationError,
      techniqueTimeline,
      currentIncidentCandidate,
      startSimulation,
      replayRun,
      pause,
      resume,
      stop,
      resetView,
      retry,
      retryScoring,
      continueTelemetryOnly,
      refreshModels,
      retryCorrelation,
      continueWithoutCorrelation,
    ],
  )
  return (
    <SimulationPlaybackContext.Provider value={value}>
      {children}
    </SimulationPlaybackContext.Provider>
  )
}
