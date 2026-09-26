import { apiClient } from './apiClient'
import type {
  DefensivePlaybook,
  ResponseAnalysisResult,
  ResponseRecommendation,
  ResponseRunSummary,
} from '../types/response'

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value))
    throw new Error('Malformed synthetic response payload.')
  return value as Record<string, unknown>
}

function recommendation(value: unknown): ResponseRecommendation {
  const item = record(value)
  if (
    typeof item.recommendation_id !== 'string' ||
    typeof item.playbook_name !== 'string' ||
    typeof item.target_id !== 'string' ||
    typeof item.rank !== 'number' ||
    typeof item.recommendation_score !== 'number' ||
    item.synthetic !== true ||
    !Array.isArray(item.evidence_summary) ||
    !Array.isArray(item.warnings)
  )
    throw new Error('Malformed synthetic recommendation.')
  if (item.simulation !== null) {
    const simulation = record(item.simulation)
    if (
      simulation.synthetic !== true ||
      !Array.isArray(simulation.changed_node_ids) ||
      !Array.isArray(simulation.changed_edge_ids) ||
      typeof simulation.correlated_paths_interrupted !== 'number' ||
      typeof simulation.predicted_paths_interrupted !== 'number'
    )
      throw new Error('Malformed synthetic impact simulation.')
  }
  return item as unknown as ResponseRecommendation
}

export async function getResponsePlaybooks(): Promise<DefensivePlaybook[]> {
  const data: unknown = (await apiClient.get('/api/v1/response/playbooks')).data
  if (!Array.isArray(data) || data.some((item) => record(item).synthetic !== true))
    throw new Error('Malformed synthetic playbook catalogue.')
  return data as DefensivePlaybook[]
}

export async function analyzeResponses(input: {
  runId: string
  modelId: string
  throughSequence?: number
  predictionEnabled: boolean
  topK?: number
  force?: boolean
}): Promise<ResponseAnalysisResult> {
  const data: unknown = (
    await apiClient.post(`/api/v1/response/runs/${encodeURIComponent(input.runId)}/analyze`, {
      model_id: input.modelId,
      through_sequence_number: input.throughSequence,
      prediction_enabled: input.predictionEnabled,
      top_k: input.topK ?? 5,
      force_reanalyze: input.force ?? false,
    })
  ).data
  const item = record(data)
  if (item.synthetic !== true || !Array.isArray(item.recommendations))
    throw new Error('Malformed synthetic response analysis.')
  return {
    ...(item as unknown as ResponseAnalysisResult),
    recommendations: item.recommendations.map(recommendation),
  }
}

export async function getResponseSummary(
  runId: string,
  modelId: string,
): Promise<ResponseRunSummary> {
  const data: unknown = (
    await apiClient.get(`/api/v1/response/runs/${encodeURIComponent(runId)}/summary`, {
      params: { model_id: modelId },
    })
  ).data
  const item = record(data)
  if (item.synthetic !== true) throw new Error('Malformed synthetic response summary.')
  return {
    ...(item as unknown as ResponseRunSummary),
    top_recommendation: item.top_recommendation ? recommendation(item.top_recommendation) : null,
  }
}
