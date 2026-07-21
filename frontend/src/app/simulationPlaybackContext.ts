import { createContext } from 'react'

import type {
  PlaybackState,
  SimulationRun,
  SimulationScenario,
  TelemetryEvent,
} from '../types/simulation'
import type { WebSocketConnectionState } from '../types/websocket'

export interface StartSimulationInput {
  scenarioId: string
  seed: number
  startTime: string
  playbackSpeed: number
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
  startSimulation: (input: StartSimulationInput) => Promise<void>
  replayRun: (run: SimulationRun) => void
  pause: () => void
  resume: () => void
  stop: () => void
  resetView: () => void
  retry: () => void
}

export const SimulationPlaybackContext = createContext<SimulationPlaybackContextValue | null>(null)
