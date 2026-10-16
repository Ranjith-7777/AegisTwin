import { isAxiosError } from 'axios'

import { apiClient } from './apiClient'
import type {
  DataSourceCatalogue,
  FlowFindingsResponse,
  NetworkFlowEvaluation,
} from '../types/dataSources'

export async function getDataSources(): Promise<DataSourceCatalogue> {
  const data = (await apiClient.get<DataSourceCatalogue>('/api/v1/data-sources')).data
  if (!Array.isArray(data.imported) || !Array.isArray(data.built_in)) {
    throw new Error('Malformed data-source catalogue.')
  }
  return data
}

/** null when no recorded-dataset evaluation has been run yet. */
export async function getLatestFlowEvaluation(): Promise<NetworkFlowEvaluation | null> {
  try {
    return (await apiClient.get<NetworkFlowEvaluation>('/api/v1/data-sources/evaluations/latest'))
      .data
  } catch (reason) {
    if (isAxiosError(reason) && reason.response?.status === 404) return null
    throw reason
  }
}

export async function getFlowFindings(sourceId: string): Promise<FlowFindingsResponse> {
  return (
    await apiClient.get<FlowFindingsResponse>(
      `/api/v1/data-sources/${encodeURIComponent(sourceId)}/findings`,
      { params: { limit: 50 } },
    )
  ).data
}
