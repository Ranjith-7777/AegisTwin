import { apiClient } from './apiClient'
import { API_BASE_URL } from '../lib/constants'
import type {
  AggregateResultView,
  BatchCreateRequest,
  BatchView,
  DefenceMode,
  ExperimentCreateRequest,
  ExperimentDetail,
  ExperimentListFilters,
  ExperimentMetrics,
  ExperimentReport,
  ExperimentStatus,
  ExperimentTimeline,
  ExperimentView,
  ModeComparisonResult,
} from '../types/evaluation'

const BASE = '/api/v1/evaluation'

export async function createExperiment(
  request: ExperimentCreateRequest,
): Promise<ExperimentDetail> {
  return (await apiClient.post<ExperimentDetail>(`${BASE}/experiments`, request)).data
}

export async function listExperiments(
  filters: ExperimentListFilters = {},
): Promise<ExperimentView[]> {
  return (
    await apiClient.get<ExperimentView[]>(`${BASE}/experiments`, {
      params: filters,
    })
  ).data
}

export async function getExperiment(experimentId: string): Promise<ExperimentDetail> {
  return (
    await apiClient.get<ExperimentDetail>(`${BASE}/experiments/${encodeURIComponent(experimentId)}`)
  ).data
}

export async function rerunExperiment(experimentId: string): Promise<ExperimentDetail> {
  return (
    await apiClient.post<ExperimentDetail>(
      `${BASE}/experiments/${encodeURIComponent(experimentId)}/rerun`,
    )
  ).data
}

/** Returns `null` when the backend reports `EXPERIMENT_METRICS_NOT_AVAILABLE`
 * (HTTP 404) - callers should treat this as a normal "not computed yet"
 * state, never as an error banner. Any other failure is re-thrown. */
export async function getExperimentMetrics(
  experimentId: string,
): Promise<ExperimentMetrics | null> {
  try {
    return (
      await apiClient.get<ExperimentMetrics>(
        `${BASE}/experiments/${encodeURIComponent(experimentId)}/metrics`,
      )
    ).data
  } catch (error) {
    const status = (error as { response?: { status?: number } }).response?.status
    if (status === 404) return null
    throw error
  }
}

export async function getExperimentTimeline(experimentId: string): Promise<ExperimentTimeline> {
  return (
    await apiClient.get<ExperimentTimeline>(
      `${BASE}/experiments/${encodeURIComponent(experimentId)}/timeline`,
    )
  ).data
}

export async function getExperimentReport(experimentId: string): Promise<ExperimentReport> {
  return (
    await apiClient.get<ExperimentReport>(
      `${BASE}/experiments/${encodeURIComponent(experimentId)}/report`,
    )
  ).data
}

/** Builds the query string shared by the CSV/JSON export endpoints, from
 * the same filter shape used by `listExperiments`. */
function exportQueryString(filters: ExperimentListFilters): string {
  const params = new URLSearchParams()
  if (filters.scenario_id) params.set('scenario_id', filters.scenario_id)
  if (filters.defence_mode) params.set('defence_mode', filters.defence_mode)
  if (filters.seed !== undefined) params.set('seed', String(filters.seed))
  if (filters.status) params.set('status', filters.status)
  if (filters.batch_id) params.set('batch_id', filters.batch_id)
  const query = params.toString()
  return query ? `?${query}` : ''
}

/** Absolute URL for the CSV export endpoint (a real file download), for use
 * in a plain `<a href download>` link - not fetched via `apiClient`. */
export function exportExperimentsCsvUrl(filters: ExperimentListFilters = {}): string {
  return `${API_BASE_URL}${BASE}/experiments/export.csv${exportQueryString(filters)}`
}

/** Absolute URL for the JSON export endpoint (a real file download), for use
 * in a plain `<a href download>` link - not fetched via `apiClient`. */
export function exportExperimentsJsonUrl(filters: ExperimentListFilters = {}): string {
  return `${API_BASE_URL}${BASE}/experiments/export.json${exportQueryString(filters)}`
}

// ---------------------------------------------------------------------
// Batches / compare / aggregate
// ---------------------------------------------------------------------

export async function createBatch(request: BatchCreateRequest): Promise<BatchView> {
  return (await apiClient.post<BatchView>(`${BASE}/batches`, request)).data
}

export async function listBatches(): Promise<BatchView[]> {
  return (await apiClient.get<BatchView[]>(`${BASE}/batches`)).data
}

export async function getBatch(batchId: string): Promise<BatchView> {
  return (await apiClient.get<BatchView>(`${BASE}/batches/${encodeURIComponent(batchId)}`)).data
}

export async function compareModes(params: {
  scenarioId: string
  seed: number
  defenceModes?: DefenceMode[]
}): Promise<ModeComparisonResult> {
  return (
    await apiClient.get<ModeComparisonResult>(`${BASE}/compare`, {
      params: {
        scenario_id: params.scenarioId,
        seed: params.seed,
        defence_modes: params.defenceModes,
      },
    })
  ).data
}

export async function aggregate(params: {
  scenarioId?: string
  defenceMode?: DefenceMode
  seeds?: number[]
  includeFailed?: boolean
  status?: ExperimentStatus
}): Promise<AggregateResultView> {
  return (
    await apiClient.get<AggregateResultView>(`${BASE}/aggregate`, {
      params: {
        scenario_id: params.scenarioId,
        defence_mode: params.defenceMode,
        seeds: params.seeds,
        include_failed: params.includeFailed,
      },
    })
  ).data
}
