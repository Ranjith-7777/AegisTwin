import { apiClient } from './apiClient'
import type {
  PurpleExperimentMode,
  PurpleTeamExperiment,
  RedScenarioSummary,
} from '../types/purpleTeam'

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value))
    throw new Error('Malformed synthetic purple team payload.')
  return value as Record<string, unknown>
}

export async function listRedScenarios(): Promise<RedScenarioSummary[]> {
  const data: unknown = (await apiClient.get('/api/v1/purple-team/scenarios')).data
  if (!Array.isArray(data) || data.some((item) => record(item).synthetic !== true))
    throw new Error('Malformed synthetic scenario catalogue.')
  return data as RedScenarioSummary[]
}

export async function runPurpleTeamExperiment(input: {
  scenarioId: string
  mode: PurpleExperimentMode
  seed?: number
  topK?: number
}): Promise<PurpleTeamExperiment> {
  const data: unknown = (
    await apiClient.post('/api/v1/purple-team/experiments', {
      scenario_id: input.scenarioId,
      mode: input.mode,
      seed: input.seed ?? 84,
      top_k: input.topK ?? 3,
    })
  ).data
  const item = record(data)
  if (item.synthetic !== true || !Array.isArray(item.steps))
    throw new Error('Malformed synthetic purple team experiment.')
  return item as unknown as PurpleTeamExperiment
}

export async function listPurpleTeamExperiments(): Promise<PurpleTeamExperiment[]> {
  const data: unknown = (await apiClient.get('/api/v1/purple-team/experiments')).data
  if (!Array.isArray(data) || data.some((item) => record(item).synthetic !== true))
    throw new Error('Malformed synthetic experiment history.')
  return data as PurpleTeamExperiment[]
}
