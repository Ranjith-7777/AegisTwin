export type AttackPathType = 'potential' | 'observed' | 'inferred' | 'predicted'

export interface AttackPathStep {
  sequence: number
  source_asset_id: string
  destination_asset_id: string
  edge_id: string
  relationship_type: string
  attack_semantics: string
  reason: string
  trust_boundary_crossed: boolean
  source_zone: string
  destination_zone: string
  privileged: boolean
  synthetic: true
}

export interface AttackPathScore {
  total: number
  exposure_contribution: number
  privilege_contribution: number
  critical_target_contribution: number
  boundary_crossing_contribution: number
  evidence_contribution: number
  length_penalty: number
}

export interface AttackPath {
  path_id: string
  path_type: AttackPathType
  source_asset_id: string
  target_asset_id: string
  ordered_asset_ids: string[]
  steps: AttackPathStep[]
  hop_count: number
  trust_boundaries_crossed: string[]
  privilege_escalation: boolean
  target_criticality: string
  target_sensitivity: string
  evidence_asset_ids: string[]
  score: AttackPathScore
  statement: string
  through_sequence_number: number | null
  synthetic: true
}

export interface AttackPathAnalysisResult {
  source_asset_id: string
  target_asset_id: string | null
  path_type: AttackPathType
  simulation_run_id: string | null
  model_id: string | null
  through_sequence_number: number | null
  max_depth: number
  max_paths: number
  paths: AttackPath[]
  total_candidates_considered: number
  synthetic: true
}
