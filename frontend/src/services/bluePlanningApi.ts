import { apiClient } from './apiClient'
import type { PlanComparisonResult } from '../types/bluePlanning'

export async function compareResponsePlans(input: {
  runId: string
  modelId: string
  incidentCandidateId: string
  throughSequence: number
  topK?: number
}): Promise<PlanComparisonResult> {
  const data = (
    await apiClient.post<PlanComparisonResult>(
      `/api/v1/blue-planning/runs/${encodeURIComponent(input.runId)}/compare`,
      {
        model_id: input.modelId,
        incident_candidate_id: input.incidentCandidateId,
        through_sequence_number: input.throughSequence,
        top_k: input.topK ?? 5,
      },
    )
  ).data
  if (!Array.isArray(data.candidates)) throw new Error('Malformed synthetic plan comparison.')
  return data
}
