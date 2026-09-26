import { apiClient } from './apiClient'
import type { AutonomyConfig, AutonomyMode } from '../types/autonomy'

export async function getAutonomyConfig(): Promise<AutonomyConfig> {
  return (await apiClient.get<AutonomyConfig>('/api/v1/autonomy')).data
}

export async function setAutonomyMode(
  mode: AutonomyMode,
  updatedBy: string,
  confirm: boolean,
): Promise<AutonomyConfig> {
  return (
    await apiClient.put<AutonomyConfig>('/api/v1/autonomy', {
      mode,
      updated_by: updatedBy,
      confirm,
    })
  ).data
}
