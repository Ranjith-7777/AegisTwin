export interface BlastRadiusScore {
  total: number
  reachable_contribution: number
  critical_asset_contribution: number
  sensitive_asset_contribution: number
  zone_crossing_contribution: number
}

export interface BlastRadiusResult {
  compromised_asset_ids: string[]
  directly_affected_asset_ids: string[]
  reachable_asset_ids: string[]
  dependent_asset_ids: string[]
  critical_assets_at_risk: string[]
  trust_zones_reached: string[]
  representative_paths: string[][]
  reachable_count: number
  dependent_count: number
  critical_count: number
  score: BlastRadiusScore
  through_sequence_number: number | null
  statement: string
  synthetic: true
}
