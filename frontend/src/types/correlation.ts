export type CorrelationState = 'monitoring' | 'correlated' | 'high_priority' | 'closed'
export interface MitreTechnique {
  technique_id: string
  name: string
  tactics: string[]
  description: string
  mapping_conditions: string
  catalogue_version: string
  source_name: string
  reference_date: string
  synthetic_demo_applicable: boolean
  synthetic: true
}
export interface TechniqueObservation {
  mapping_id: string
  technique_id: string
  technique_name: string
  event_id: string
  sequence_number: number
  mapping_confidence: number
  evidence_fields: Record<string, unknown>
  rationale: string
  tactic: string
  mapper_version: string
  model_id: string
  synthetic: true
}
export interface IncidentCandidate {
  incident_candidate_id: string
  simulation_run_id: string
  model_id: string
  title: string
  summary?: string
  correlation_state: CorrelationState
  priority: string
  correlation_score: number
  component_scores: Record<string, number>
  first_sequence_number: number
  latest_sequence_number: number
  primary_user_id: string | null
  primary_device_id: string | null
  involved_asset_ids: string[]
  observed_tactic_ids: string[]
  observed_technique_ids: string[]
  evidence_count: number
  synthetic: true
}
export interface IncidentEvidence {
  evidence_id: string
  event_id: string
  assessment_id: string | null
  technique_mapping_id: string | null
  sequence_number: number
  evidence_type: string
  contribution_score: number
  rationale: string
  synthetic: true
}
export interface CorrelationAnalysisResult {
  simulation_run_id: string
  model_id: string
  incident_candidate_id: string | null
  technique_observation_count: number
  evidence_count: number
  snapshot_count: number
  synthetic: true
}
export interface IncidentPage {
  items: IncidentCandidate[]
  total: number
  page: number
  page_size: number
  pages: number
}
export interface TechniqueObservationPage {
  items: TechniqueObservation[]
  total: number
  page: number
  page_size: number
  pages: number
}
