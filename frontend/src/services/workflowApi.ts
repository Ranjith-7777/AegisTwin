import { apiClient } from './apiClient'
import type { WorkflowRunResult } from '../types/workflow'

export async function runWorkflowCoordinator(input: {
  runId: string
  modelId: string
  incidentCandidateId: string
  throughSequence: number
  topK?: number
}): Promise<WorkflowRunResult> {
  const data = (
    await apiClient.post<WorkflowRunResult>(
      `/api/v1/workflow/runs/${encodeURIComponent(input.runId)}/execute`,
      {
        model_id: input.modelId,
        incident_candidate_id: input.incidentCandidateId,
        through_sequence_number: input.throughSequence,
        top_k: input.topK ?? 5,
      },
    )
  ).data
  if (data.comparison !== null && !Array.isArray(data.comparison.candidates))
    throw new Error('Malformed synthetic workflow result.')
  return data
}
