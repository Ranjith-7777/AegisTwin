export type PurpleExperimentMode = 'observe_only' | 'defense_enabled'

export type RedStepOutcome =
  'attempted' | 'succeeded_synthetic' | 'failed_precondition' | 'blocked_synthetic' | 'skipped'

export interface RedScenarioTechniqueSummary {
  step_sequence: number
  technique_id: string | null
  technique_name: string | null
  tactic: string | null
  rationale: string
}

export interface RedScenarioSummary {
  scenario_id: string
  name: string
  description: string
  is_red_agent_scenario: boolean
  step_count: number
  mitre_technique_ids: string[]
  step_techniques: RedScenarioTechniqueSummary[]
  synthetic: true
}

export interface PurpleTeamStepResult {
  step_result_id: string
  experiment_id: string
  step_sequence: number
  description: string
  event_id: string | null
  target_asset_id: string | null
  expected_technique_id: string | null
  expected_technique_name: string | null
  outcome: RedStepOutcome
  detected: boolean
  anomaly_score: number | null
  classification: string | null
  observed_technique_ids: string[]
  incident_candidate_id: string | null
  response_recommendation_id: string | null
  orchestration_id: string | null
  orchestration_state: string | null
  synthetic: true
}

export interface PurpleTeamSummary {
  total_steps: number
  attempted_steps: number
  succeeded_synthetic_steps: number
  detected_steps: number
  missed_steps: number
  expected_detectable_steps: number
  detection_step_coverage: number | null
  mitre_techniques_exercised: string[]
  mitre_techniques_observed: string[]
  incident_created: boolean
  first_detection_sequence: number | null
  response_recommendation_created: boolean
  response_executed: boolean
  verification_result: string | null
  critical_assets_reached: string[]
  estimated_blast_radius_count: number | null
  final_outcome: string
}

export interface PurpleTeamExperiment {
  experiment_id: string
  scenario_id: string
  scenario_name: string
  mode: PurpleExperimentMode
  seed: number
  simulation_run_id: string | null
  model_id: string | null
  status: 'pending' | 'running' | 'completed' | 'failed'
  error: string | null
  created_at: string
  completed_at: string | null
  steps: PurpleTeamStepResult[]
  summary: PurpleTeamSummary | null
  synthetic: true
}
