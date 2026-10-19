import { apiClient } from './apiClient'
import type { SessionView } from '../types/session'

export async function getSession(): Promise<SessionView> {
  return (await apiClient.get<SessionView>('/api/v1/session')).data
}
