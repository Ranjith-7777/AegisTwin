import { createContext } from 'react'

import type {
  PlaybackState,
  SimulationRun,
  SimulationScenario,
  TelemetryEvent,
} from '../types/simulation'
import type { WebSocketConnectionState } from '../types/websocket'
import type { AnomalyAssessment, DetectionModel, ScoringStatus } from '../types/detection'
import type { IncidentCandidate, TechniqueObservation } from '../types/correlation'
import type { PredictionSnapshot } from '../types/prediction'
import type { LiveTopologyOverlay } from '../types/liveTopology'

export interface StartSimulationInput {
  scenarioId: string
  seed: number
  startTime: string
  playbackSpeed: number
  detectionEnabled: boolean
  modelId?: string
  correlationEnabled: boolean
  predictionEnabled: boolean
  topK: number
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
  correlationEnabled: boolean
  correlationStatus: 'idle' | 'analyzing' | 'ready' | 'error'
  correlationError: string | null
  techniqueTimeline: TechniqueObservation[]
  currentIncidentCandidate: IncidentCandidate | null
  predictionEnabled: boolean
  predictionStatus: 'idle' | 'analyzing' | 'ready' | 'error'
  predictionError: string | null
  predictionTimeline: PredictionSnapshot[]
  currentPrediction: PredictionSnapshot | null
  liveTopology: LiveTopologyOverlay
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
  retryCorrelation: () => Promise<void>
  continueWithoutCorrelation: () => void
  retryPrediction: () => Promise<void>
  continueWithoutPrediction: () => void
  resetTopologyOverlay: () => void
}

export const SimulationPlaybackContext = createContext<SimulationPlaybackContextValue | null>(null)
