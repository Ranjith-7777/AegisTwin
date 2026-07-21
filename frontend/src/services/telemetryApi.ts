import { apiClient } from './apiClient'
import type { TelemetryEventPage } from '../types/simulation'

export async function getTelemetryEvents(
  runId: string,
  page = 1,
  pageSize = 50,
): Promise<TelemetryEventPage> {
  return (
    await apiClient.get<TelemetryEventPage>('/api/v1/telemetry/events', {
      params: { simulation_run_id: runId, page, page_size: pageSize },
    })
  ).data
}
