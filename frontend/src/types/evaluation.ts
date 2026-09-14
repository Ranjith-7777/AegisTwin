/**
 * Phase 5 Evaluation & Reports domain types. Mirrors
 * `app/schemas/evaluation.py` field-for-field (snake_case, matching this
 * codebase's convention of not re-casing backend response shapes - see
 * `types/agents.ts`/`types/bluePlanning.ts`). Do not add fields the backend
 * schema does not declare.
 */

export type DefenceMode = 'no_active_defence' | 'rule_based' | 'ml_assisted' | 'agentic'

export type ExperimentStatus =
  'created' | 'running_attack' | 'detecting' | 'responding' | 'verifying' | 'completed' | 'failed'

export const DEFENCE_MODE_LABELS: Record<DefenceMode, string> = {
  no_active_defence: 'NO ACTIVE DEFENCE',
  rule_based: 'RULE-BASED',
  ml_assisted: 'ML-ASSISTED',
  agentic: 'AGENTIC',
}

export const ALL_DEFENCE_MODES: DefenceMode[] = [
  'no_active_defence',
  'rule_based',
  'ml_assisted',
  'agentic',
]

/** Mirrors `app.services.evaluation.batch_service.CANONICAL_SEEDS` (PM spec
 * Section 31/92) - the canonical seed set used for the full evaluation
 * matrix. Any seed may still be typed; this is only a convenience default. */
export const CANONICAL_SEEDS: number[] = [17, 42, 84, 99, 123]

/** Mirrors `app.services.evaluation.batch_service.CANONICAL_SCENARIO_MATRIX`
 * - the PM spec's four named "scenario classes" mapped onto this codebase's
 * actual scenario catalogue. */
export const CANONICAL_SCENARIO_MATRIX: Record<string, string> = {
  ddos_service_saturation: 'ddos-traffic-spike',
  credential_compromise: 'credential-compromise',
  iam_privilege_escalation: 'staged-compromise-demo',
  workload_service_compromise: 'suspicious-kubernetes-pod',
}

export const CANONICAL_SCENARIO_IDS: string[] = Object.values(CANONICAL_SCENARIO_MATRIX)

export interface ExperimentCreateRequest {
  scenario_id: string
  seed: number
  defence_mode: DefenceMode
  top_k?: number
  through_sequence?: number | null
  label?: string | null
  notes?: string | null
  perturbation_id?: string | null
  perturbation_params?: Record<string, unknown> | null
}

export interface ExperimentView {
  experiment_id: string
  scenario_id: string
  scenario_name: string
  seed: number
  defence_mode: DefenceMode
  detection_model_id: string | null
  topology_version: string
  red_scenario_version: string
  autonomy_mode: string | null
  configuration_json: Record<string, unknown>
  started_at: string | null
  ended_at: string | null
  run_id: string | null
  incident_candidate_id: string | null
  orchestration_id: string | null
  status: ExperimentStatus
  failure_stage: string | null
  failure_code: string | null
  failure_message: string | null
  verification_status: string | null
  batch_id: string | null
  rerun_of_experiment_id: string | null
  synthetic: true
  created_at: string
}

/** The `{value, applicable, note}` wrapper used throughout
 * `normalized_metrics` (and, per the backend docstring, left as
 * `Record<string, unknown>` at the schema boundary since its exact key set
 * is owned by `metrics_service`/`resilience_score_service`, not the API
 * schema). */
export interface Metric {
  value: number | boolean | null
  applicable: boolean
  note?: string | null
}

export interface ExperimentMetrics {
  metrics_version: string
  logical_timeline: Record<string, unknown>
  computation_latency: Record<string, unknown>
  raw_metrics: Record<string, unknown>
  normalized_metrics: Record<string, Metric>
  computed_at: string
  mci: number | null
  mci_version: string | null
  ars_total: number | null
  ars_pillars: ArsPillars | null
  ars_version: string | null
}

/** One raw component inside a pillar's decomposition (e.g.
 * `detection_coverage` inside pillar A), exactly as persisted by
 * `resilience_score_service._weighted_pillar`. */
export interface ArsPillarComponent {
  raw_value: number | boolean | null
  weight: number
  effective_weight: number
  applicable: boolean
}

/** One pillar (A = Threat Awareness, W = Withstand/Containment,
 * M = Mission Preservation, R = Verified Recovery) of the Aegis Resilience
 * Score decomposition, exactly as persisted in `ars_pillars_json` by
 * `resilience_score_service.ResilienceScoreService.compute`. */
export interface ArsPillar {
  value: number | null
  applicable: boolean
  note?: string | null
  components?: Record<string, ArsPillarComponent>
}

/** Real persisted shape: the four pillar letters plus a sibling
 * `effective_pillar_weights` map (top-level renormalized weights, only
 * relevant when a whole pillar is N/A) - see
 * `resilience_score_service.ResilienceScoreService.compute`. */
export interface ArsPillars {
  A?: ArsPillar
  W?: ArsPillar
  M?: ArsPillar
  R?: ArsPillar
  effective_pillar_weights?: Record<string, number>
}

export interface MissionHealthPoint {
  sequence: number
  logical_time_sim: number
  mission_health: number
  stage: string
  reason: string
}

export type TimelineEventStatus = 'occurred' | 'skipped_not_applicable' | 'failed'

export interface TimelineEvent {
  sequence: number
  stage: string
  logical_time_sim: number | null
  wall_clock_time: string | null
  status: TimelineEventStatus
  summary: string
  resource_ids: string[]
  correlation_id: string | null
  causation_id: string | null
}

export interface ExperimentTimeline {
  experiment_id: string
  events: TimelineEvent[]
  synthetic: true
}

export interface ExperimentDetail extends ExperimentView {
  metrics: ExperimentMetrics | null
  mission_health_curve: MissionHealthPoint[]
  timeline: ExperimentTimeline | null
}

// ---------------------------------------------------------------------
// Batches / comparison / aggregate - types only for now (Stage 2 wires the
// UI for these); kept here so Stage 2 does not have to re-derive the shape.
// ---------------------------------------------------------------------

export interface BatchView {
  batch_id: string
  scenario_ids: string[]
  seeds: number[]
  defence_modes: string[]
  status: string
  total_experiments: number
  completed_count: number
  failed_count: number
  experiment_ids: string[]
  max_experiments: number | null
  truncated: boolean
  started_at: string | null
  ended_at: string | null
  runtime_seconds: number | null
  created_at: string
  synthetic: true
}

export interface BatchCreateRequest {
  scenario_ids: string[]
  seeds: number[]
  defence_modes: DefenceMode[]
  max_experiments?: number | null
}

export interface MetricSummaryView {
  count: number
  n_applicable: number
  mean: number | null
  median: number | null
  std: number | null
  minimum: number | null
  maximum: number | null
}

export interface BooleanOutcomeSummaryView {
  total_applicable: number
  success_count: number
  success_rate: number | null
}

export interface AggregateResultView {
  group_label: string
  experiment_count: number
  metric_summaries: Record<string, MetricSummaryView>
  boolean_summaries: Record<string, BooleanOutcomeSummaryView>
}

export interface MetricCell {
  value: number | boolean | null
  applicable: boolean
}

export interface ComparisonRow {
  metric: string
  values: Record<string, MetricCell>
}

export interface PairedDelta {
  metric: string
  reference_mode: string
  compared_mode: string
  reference_value: number | null
  compared_value: number | null
  delta: number | null
  paired: boolean
  fairness_reasons: string[]
}

export interface ModeComparisonResult {
  scenario_id: string
  seed: number
  baseline_mode: string | null
  available_modes: string[]
  missing_modes: string[]
  rows: ComparisonRow[]
  paired_deltas: PairedDelta[]
  synthetic: true
}

export interface ExperimentReport {
  experiment_id: string
  executive_summary: string
  configuration: Record<string, unknown>
  attack_techniques_observed: string[]
  detection_evidence_summary: Record<string, unknown>
  incident_summary: Record<string, unknown> | null
  attack_graph_and_blast_radius: Record<string, unknown>
  response_verification_rollback_summary: Record<string, unknown>
  metrics: ExperimentMetrics | null
  mission_continuity_index: number | null
  ars_decomposition: Record<string, unknown> | null
  paired_baseline_comparison: ModeComparisonResult | null
  limitations: string[]
  reproduction: Record<string, unknown>
  synthetic: true
}

export interface ExperimentListFilters {
  scenario_id?: string
  defence_mode?: DefenceMode
  seed?: number
  status?: ExperimentStatus
  batch_id?: string
}
