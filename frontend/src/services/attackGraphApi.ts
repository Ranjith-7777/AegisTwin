import { apiClient } from './apiClient'
import type { AttackPathAnalysisResult, AttackPathType } from '../types/attackGraph'

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value))
    throw new Error('Malformed synthetic attack graph payload.')
  return value as Record<string, unknown>
}

export async function analyzeAttackPaths(input: {
  sourceAssetId: string
  targetAssetId?: string
  pathType?: AttackPathType
  runId?: string
  modelId?: string
  throughSequence?: number
  maxDepth?: number
  maxPaths?: number
}): Promise<AttackPathAnalysisResult> {
  const data: unknown = (
    await apiClient.get('/api/v1/attack-graph/paths', {
      params: {
        source_asset_id: input.sourceAssetId,
        target_asset_id: input.targetAssetId,
        path_type: input.pathType ?? 'potential',
        simulation_run_id: input.runId,
        model_id: input.modelId,
        through_sequence_number: input.throughSequence,
        max_depth: input.maxDepth,
        max_paths: input.maxPaths,
      },
    })
  ).data
  const item = record(data)
  if (item.synthetic !== true || !Array.isArray(item.paths))
    throw new Error('Malformed synthetic attack path analysis.')
  return item as unknown as AttackPathAnalysisResult
}
