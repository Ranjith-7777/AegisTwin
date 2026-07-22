export type DetectionClassification = 'normal' | 'anomalous'
export type ScoringStatus = 'idle' | 'scoring' | 'ready' | 'error'

export interface DetectionModel {
  model_id: string
  model_type: string
  model_version: string
  feature_schema_version: string
  calibration_version: string
  calibration_method: string
  dataset_fingerprint: string
  random_state: number
  target_false_positive_rate: number
  calibrated_threshold: number
  threshold_percentile: number
  training_event_count: number
  validation_event_count: number
  created_at: string
  synthetic: boolean
  configuration_json: Record<string, unknown>
}

export interface SeedRange {
  start: number
  end: number
}
export interface DetectionTrainingRequest {
  training_seed_range: SeedRange
  validation_seed_range: SeedRange
  evaluation_seed_range: SeedRange
  random_state: number
  target_false_positive_rate: number
}
export interface DetectionTrainingResult {
  model_id: string
  model_type: string
  feature_schema_version: string
  training_event_count: number
  validation_event_count: number
  dataset_fingerprint: string
  calibrated_threshold: number
  target_false_positive_rate: number
  synthetic: boolean
}
export interface RunScoringResult {
  model_id: string
  simulation_run_id: string
  assessment_count: number
  anomalous_count: number
  force_rescore: boolean
  synthetic: boolean
}
export interface ComponentScores {
  isolation_forest: number
  robust_numerical_deviation: number
  categorical_rarity: number
  behavioural_transition_rarity: number
  infrastructure_novelty: number
  [key: string]: number
}
export interface AnomalyAssessment {
  assessment_id: string
  model_id: string
  event_id: string
  sequence_number: number
  feature_schema_version: string
  calibration_method: string
  detector_type: string
  raw_isolation_forest_score: number
  isolation_forest_rank: number
  hybrid_anomaly_score: number
  threshold: number
  classification: DetectionClassification
  contributing_signals: string[]
  component_scores: ComponentScores
  synthetic: true
}
export interface ModelEvaluation {
  evaluation_id: string
  model_id: string
  precision: number
  recall: number
  f1_score: number
  false_positive_rate: number
  feature_schema_version: string
  calibration_method: string
  event_level_metrics: Record<string, number>
  scenario_wide_metrics: Record<string, number>
  run_level_metrics: Record<string, number>
  pure_isolation_metrics: Record<string, number>
  baseline_metrics: Record<string, unknown>
  hybrid_metrics: Record<string, number>
  synthetic: boolean
}
