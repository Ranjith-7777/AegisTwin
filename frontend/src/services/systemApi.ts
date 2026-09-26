import { apiClient } from './apiClient'
import type { HealthResponse, SafetyResponse, SystemStatusResponse } from '../types/api'

export async function getHealth(): Promise<HealthResponse> {
  return (await apiClient.get<HealthResponse>('/api/health')).data
}

export async function getSystemStatus(): Promise<SystemStatusResponse> {
  return (await apiClient.get<SystemStatusResponse>('/api/system/status')).data
}

export async function getSafetyStatus(): Promise<SafetyResponse> {
  return (await apiClient.get<SafetyResponse>('/api/safety')).data
}
