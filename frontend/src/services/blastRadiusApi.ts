import { apiClient } from './apiClient'
import type { BlastRadiusResult } from '../types/blastRadius'

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value))
    throw new Error('Malformed synthetic blast radius payload.')
  return value as Record<string, unknown>
}

export async function estimateBlastRadius(input: {
  compromisedAssetIds: string[]
  runId?: string
  throughSequence?: number
  maxDepth?: number
}): Promise<BlastRadiusResult> {
  const data: unknown = (
    await apiClient.post('/api/v1/blast-radius', {
      compromised_asset_ids: input.compromisedAssetIds,
      simulation_run_id: input.runId,
      through_sequence_number: input.throughSequence,
      max_depth: input.maxDepth,
    })
  ).data
  const item = record(data)
  if (item.synthetic !== true || !Array.isArray(item.reachable_asset_ids))
    throw new Error('Malformed synthetic blast radius estimate.')
  return item as unknown as BlastRadiusResult
}
