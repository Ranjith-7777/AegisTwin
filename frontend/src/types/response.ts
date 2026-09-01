export type ApprovalTier =
  'automatic_candidate' | 'analyst_approval' | 'administrator_approval' | 'prohibited'

export interface DefensivePlaybook {
  playbook_id: string
  playbook_version: string
  name: string
  description: string
  action_type: string
  supported_target_types: string[]
  required_evidence: string[]
  disqualifying_conditions: string[]
  topology_mutation_specification: Record<string, unknown>
  reversibility: string
  default_operational_impact: string
  default_blast_radius: string
  approval_tier: ApprovalTier
  automatic_eligibility: boolean
  synthetic: true
  catalogue_version: string
  resource_cost_weight?: number
  sla_sensitivity_weight?: number
}

/** Blue Agent objective components behind Defense Score. */
export interface DefenseComponents {
  security_improvement: number
  service_disruption: number
  resource_cost: number
  sla_penalty: number
  defense_score: number
}

export interface ResponseImpactSimulation {
  simulation_id: string
  recommendation_id: string
  run_id: string
  through_sequence_number: number
  base_topology_version: string
  simulation_engine_version: string
  target_type: string
  target_id: string
  changed_node_ids: string[]
  changed_edge_ids: string[]
  paths_before: Array<Record<string, unknown>>
  paths_after: Array<Record<string, unknown>>
  correlated_paths_interrupted: number
  predicted_paths_interrupted: number
  sensitive_assets_reachable_before: number
  sensitive_assets_reachable_after: number
  expected_relationships_affected: number
  affected_asset_count: number
  affected_edge_count: number
  interruption_score: number
  residual_exposure_score: number
  operational_disruption_score: number
  blast_radius: string
  reversibility: string
  approval_tier: ApprovalTier
  warnings: string[]
  synthetic: true
  created_at: string
}

export interface ResponseRecommendation {
  recommendation_id: string
  response_analysis_id: string
  run_id: string
  model_id: string
  incident_candidate_id: string
  prediction_snapshot_id: string | null
  through_sequence_number: number
  playbook_id: string
  playbook_name: string
  target_type: string
  target_id: string
  rank: number
  recommendation_score: number
  component_scores: Record<string, number>
  penalties: Record<string, number>
  defense_score: number
  defense_components: DefenseComponents
  defense_explanation: string
  required_approval_tier: ApprovalTier
  recommendation_state: string
  evidence_summary: string[]
  rationale: string
  warnings: string[]
  synthetic: true
  created_at: string
  simulation: ResponseImpactSimulation | null
}

export interface ResponseAnalysisResult {
  response_analysis_id: string
  run_id: string
  model_id: string
  incident_candidate_id: string
  prediction_snapshot_id: string | null
  through_sequence_number: number
  response_engine_version: string
  recommendation_count: number
  recommendations: ResponseRecommendation[]
  force_reanalyze: boolean
  synthetic: true
  created_at: string
}

export interface ResponseRunSummary {
  run_id: string
  model_id: string
  through_sequence_number: number
  recommendation_count: number
  top_recommendation: ResponseRecommendation | null
  analysis_sequence: number
  synthetic: true
}
