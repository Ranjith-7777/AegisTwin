import { apiClient } from './apiClient'
import type {
  PredictionAnalysisResult,
  PredictionEvaluation,
  PredictionSnapshot,
  PredictionSnapshotPage,
} from '../types/prediction'

export async function analyzePredictions(
  runId: string,
  modelId: string,
  topK = 3,
  force_reanalyze = false,
): Promise<PredictionAnalysisResult> {
  return (
    await apiClient.post<PredictionAnalysisResult>(
      `/api/v1/prediction/runs/${encodeURIComponent(runId)}/analyze`,
      { model_id: modelId, top_k: topK, force_reanalyze },
    )
  ).data
}

export async function getPredictionSnapshots(
  runId: string,
  modelId: string,
): Promise<PredictionSnapshotPage> {
  return (
    await apiClient.get<PredictionSnapshotPage>(
      `/api/v1/prediction/runs/${encodeURIComponent(runId)}/snapshots`,
      { params: { model_id: modelId, page_size: 100 } },
    )
  ).data
}

export async function getLatestPrediction(
  runId: string,
  modelId: string,
): Promise<PredictionSnapshot> {
  return (
    await apiClient.get<PredictionSnapshot>(
      `/api/v1/prediction/runs/${encodeURIComponent(runId)}/latest`,
      { params: { model_id: modelId } },
    )
  ).data
}

export async function evaluatePredictions(
  runId: string,
  modelId: string,
): Promise<PredictionEvaluation> {
  return (
    await apiClient.post<PredictionEvaluation>(
      `/api/v1/prediction/runs/${encodeURIComponent(runId)}/evaluate`,
      { model_id: modelId },
    )
  ).data
}
