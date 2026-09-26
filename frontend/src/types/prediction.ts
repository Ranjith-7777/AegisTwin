export type PredictionHypothesisType =
  'next_technique' | 'next_tactic' | 'next_asset' | 'likely_objective'

export interface PredictionHypothesis {
  hypothesis_id: string
  prediction_snapshot_id: string
  rank: number
  hypothesis_type: PredictionHypothesisType
  predicted_technique_id: string | null
  predicted_technique_name: string | null
  predicted_tactic: string | null
  predicted_asset_id: string | null
  predicted_objective: string | null
  prediction_score: number
  component_scores: Record<string, number>
  prerequisite_evidence: string[]
  contradictory_evidence: string[]
  rationale: string
  synthetic: true
}

export interface PredictionSnapshot {
  prediction_snapshot_id: string
  simulation_run_id: string
  model_id: string
  incident_candidate_id: string | null
  through_sequence_number: number
  predictor_version: string
  progression_catalogue_version: string
  prediction_state: string
  current_stage_estimate: string
  current_tactic_estimate: string
  observed_technique_ids: string[]
  observed_tactic_ids: string[]
  candidate_hypothesis_count: number
  insufficient_evidence_reason: string | null
  supporting_evidence: string[]
  hypotheses: PredictionHypothesis[]
  synthetic: true
  created_at: string
}

export interface PredictionAnalysisResult {
  simulation_run_id: string
  model_id: string
  snapshot_count: number
  hypothesis_count: number
  predictor_version: string
  progression_catalogue_version: string
  top_k: number
  force_reanalyze: boolean
  synthetic: true
}

export interface PredictionSnapshotPage {
  items: PredictionSnapshot[]
  page: number
  page_size: number
  total: number
  pages: number
}

export interface PredictionEvaluation {
  evaluation_id: string
  simulation_run_id: string
  model_id: string
  predictor_version: string
  metrics: Record<string, unknown>
  baseline_metrics: Record<string, unknown>
  truth_manifest_version: string
  synthetic: true
  created_at: string
}
