import { apiClient } from './apiClient'
import type {
  CorrelationAnalysisResult,
  IncidentEvidence,
  IncidentPage,
  MitreTechnique,
  TechniqueObservationPage,
} from '../types/correlation'

export async function analyzeRun(
  runId: string,
  modelId: string,
  force_reanalyze = false,
): Promise<CorrelationAnalysisResult> {
  return (
    await apiClient.post<CorrelationAnalysisResult>(
      `/api/v1/correlation/runs/${encodeURIComponent(runId)}/analyze`,
      { model_id: modelId, force_reanalyze },
    )
  ).data
}
export async function getRunIncidents(runId: string): Promise<IncidentPage> {
  return (
    await apiClient.get<IncidentPage>(
      `/api/v1/correlation/runs/${encodeURIComponent(runId)}/incidents`,
    )
  ).data
}
export async function getRunTechniques(runId: string): Promise<TechniqueObservationPage> {
  return (
    await apiClient.get<TechniqueObservationPage>(
      `/api/v1/correlation/runs/${encodeURIComponent(runId)}/techniques`,
    )
  ).data
}
export async function getIncidentEvidence(id: string): Promise<IncidentEvidence[]> {
  return (
    await apiClient.get<IncidentEvidence[]>(
      `/api/v1/correlation/incidents/${encodeURIComponent(id)}/evidence`,
    )
  ).data
}
export async function getMitreTechniques(): Promise<MitreTechnique[]> {
  return (await apiClient.get<MitreTechnique[]>('/api/v1/mitre/techniques')).data
}
