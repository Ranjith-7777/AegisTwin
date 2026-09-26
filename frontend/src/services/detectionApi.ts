import { apiClient } from './apiClient'
import type {
  DetectionModel,
  DetectionTrainingRequest,
  DetectionTrainingResult,
  ModelEvaluation,
  RunScoringResult,
} from '../types/detection'

export async function getDetectionModels(): Promise<DetectionModel[]> {
  return (await apiClient.get<DetectionModel[]>('/api/v1/detection/models')).data
}
export async function trainDetectionModel(
  request: DetectionTrainingRequest,
): Promise<DetectionTrainingResult> {
  return (await apiClient.post<DetectionTrainingResult>('/api/v1/detection/models/train', request))
    .data
}
export async function scoreSimulationRun(
  runId: string,
  modelId: string,
  forceRescore = false,
): Promise<RunScoringResult> {
  return (
    await apiClient.post<RunScoringResult>(
      `/api/v1/detection/runs/${encodeURIComponent(runId)}/score`,
      { model_id: modelId, force_rescore: forceRescore },
    )
  ).data
}
export async function evaluateDetectionModel(modelId: string): Promise<ModelEvaluation> {
  return (
    await apiClient.post<ModelEvaluation>(
      `/api/v1/detection/models/${encodeURIComponent(modelId)}/evaluate`,
    )
  ).data
}
