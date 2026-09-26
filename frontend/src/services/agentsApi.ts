import { apiClient } from './apiClient'
import type { AgentRegistry, AgentTrace } from '../types/agents'

function valid(value: unknown, key: string): boolean {
  return Boolean(value && typeof value === 'object' && key in value)
}

export async function getAgentRegistry(): Promise<AgentRegistry> {
  const data = (await apiClient.get<AgentRegistry>('/api/v1/agents')).data
  if (!valid(data, 'total_agents')) throw new Error('Malformed synthetic agent registry.')
  return data
}

export async function getAgentTrace(orchestrationId: string): Promise<AgentTrace> {
  const data = (
    await apiClient.get<AgentTrace>(
      `/api/v1/agents/orchestrations/${encodeURIComponent(orchestrationId)}/trace`,
    )
  ).data
  if (!valid(data, 'entries')) throw new Error('Malformed synthetic agent trace.')
  return data
}
