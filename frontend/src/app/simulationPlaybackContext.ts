import { createContext } from 'react'

import type {
  PlaybackState,
  SimulationRun,
  SimulationScenario,
  TelemetryEvent,
} from '../types/simulation'
import type { WebSocketConnectionState } from '../types/websocket'
import type { AnomalyAssessment, DetectionModel, ScoringStatus } from '../types/detection'

export interface StartSimulationInput {
  scenarioId: string
  seed: number
  startTime: string
  playbackSpeed: number
  detectionEnabled: boolean
  modelId?: string
}

export interface SimulationPlaybackContextValue {
  scenarios: SimulationScenario[]
  runs: SimulationRun[]
  activeRun: SimulationRun | null
  events: TelemetryEvent[]
  playbackState: PlaybackState
  connectionState: WebSocketConnectionState
  currentEventIndex: number
  totalEventCount: number
  simulatedElapsedSeconds: number
  loadingScenarios: boolean
  starting: boolean
  error: string | null
  detectionEnabled: boolean
  selectedModel: DetectionModel | null
  models: DetectionModel[]
  modelsLoading: boolean
  scoringStatus: ScoringStatus
  detectionError: string | null
  assessmentsByEventId: Record<string, AnomalyAssessment>
  assessmentTimeline: AnomalyAssessment[]
  currentAssessment: AnomalyAssessment | null
  startSimulation: (input: StartSimulationInput) => Promise<void>
  replayRun: (run: SimulationRun) => void
  pause: () => void
  resume: () => void
  stop: () => void
  resetView: () => void
  retry: () => void
  retryScoring: () => Promise<void>
  continueTelemetryOnly: () => void
  refreshModels: () => Promise<void>
}

export const SimulationPlaybackContext = createContext<SimulationPlaybackContextValue | null>(null)
