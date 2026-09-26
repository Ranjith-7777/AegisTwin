import { apiClient } from './apiClient'
import type {
  PlaybackMetadata,
  SimulationRun,
  SimulationRunCreate,
  SimulationScenario,
} from '../types/simulation'

export async function getScenarios(): Promise<SimulationScenario[]> {
  return (await apiClient.get<SimulationScenario[]>('/api/v1/simulation/scenarios')).data
}

export async function createSimulationRun(request: SimulationRunCreate): Promise<SimulationRun> {
  return (await apiClient.post<SimulationRun>('/api/v1/simulation/runs', request)).data
}

export async function getSimulationRuns(): Promise<SimulationRun[]> {
  return (await apiClient.get<SimulationRun[]>('/api/v1/simulation/runs')).data
}

export async function getPlaybackMetadata(runId: string): Promise<PlaybackMetadata> {
  return (
    await apiClient.get<PlaybackMetadata>(
      `/api/v1/simulation/runs/${encodeURIComponent(runId)}/playback`,
    )
  ).data
}
