import type { CandidatePlanAssessment, PlanComparisonResult } from '../../types/bluePlanning'
import type { IncidentCandidate } from '../../types/correlation'
import type { AnomalyAssessment } from '../../types/detection'
import type { Orchestration } from '../../types/orchestration'
import type { PredictionSnapshot } from '../../types/prediction'
import type { SimulationRun } from '../../types/simulation'
import type { StageInputs } from '../../lib/workflowStages'
import type { WorkflowRunResult } from '../../types/workflow'

export const run: SimulationRun = {
  simulation_run_id: 'run-1',
  scenario_id: 'staged-compromise-demo',
  seed: 84,
  start_time: '2026-07-21T09:00:00Z',
  playback_speed: 20,
  status: 'completed',
  event_count: 12,
  created_at: '2026-07-21T09:00:00Z',
}

export function assessment(sequence: number, anomalous: boolean): AnomalyAssessment {
  return {
    assessment_id: `a-${String(sequence)}`,
    model_id: 'model-1',
    event_id: `e-${String(sequence)}`,
    sequence_number: sequence,
    feature_schema_version: 'synthetic-behaviour-v2',
    calibration_method: 'interpolated-ecdf-v2',
    detector_type: 'IsolationForest',
    raw_isolation_forest_score: 0.1,
    isolation_forest_rank: 0.5,
    hybrid_anomaly_score: anomalous ? 0.95 : 0.2,
    threshold: 0.9,
    classification: anomalous ? 'anomalous' : 'normal',
    contributing_signals: [],
    component_scores: {} as AnomalyAssessment['component_scores'],
    synthetic: true,
  }
}

export const incident: IncidentCandidate = {
  incident_candidate_id: 'inc-1',
  simulation_run_id: 'run-1',
  model_id: 'model-1',
  title: 'Related unusual synthetic activity',
  correlation_state: 'high_priority',
  priority: 'high',
  correlation_score: 0.79,
  component_scores: {},
  first_sequence_number: 5,
  latest_sequence_number: 12,
  primary_user_id: null,
  primary_device_id: null,
  involved_asset_ids: ['external-user-01', 'api-gateway-01'],
  observed_tactic_ids: [],
  observed_technique_ids: ['T1078', 'T1110.001'],
  evidence_count: 9,
  synthetic: true,
}

export function snapshot(hypotheses: number): PredictionSnapshot {
  return {
    prediction_snapshot_id: `p-${String(hypotheses)}`,
    simulation_run_id: 'run-1',
    model_id: 'model-1',
    incident_candidate_id: 'inc-1',
    through_sequence_number: 10,
    predictor_version: 'hybrid-progression-v1',
    progression_catalogue_version: 'v1',
    prediction_state: hypotheses ? 'ranked' : 'concluded',
    current_stage_estimate: 'lateral',
    current_tactic_estimate: 'TA0008',
    observed_technique_ids: [],
    observed_tactic_ids: [],
    candidate_hypothesis_count: hypotheses,
    insufficient_evidence_reason: hypotheses ? null : 'The synthetic run has concluded.',
    supporting_evidence: [],
    hypotheses: Array.from({ length: hypotheses }, (_, index) => ({
      hypothesis_id: `h-${String(index)}`,
      prediction_snapshot_id: 'p',
      rank: index + 1,
      hypothesis_type: 'technique' as PredictionSnapshot['hypotheses'][number]['hypothesis_type'],
      predicted_technique_id: 'T1567',
      predicted_technique_name: 'Exfiltration Over Web Service',
      predicted_tactic: 'exfiltration',
      predicted_asset_id: 'object-storage-01',
      predicted_objective: null,
      prediction_score: 0.85 - index * 0.1,
      component_scores: {},
      prerequisite_evidence: [],
      contradictory_evidence: [],
      rationale: 'Observed credential access precedes exfiltration.',
      synthetic: true as const,
    })),
    synthetic: true,
    created_at: '2026-07-21T09:00:00Z',
  }
}

export function candidate(
  overrides: Partial<CandidatePlanAssessment> = {},
): CandidatePlanAssessment {
  return {
    recommendation_id: 'rec-1',
    playbook_id: 'quarantine-synthetic-ingress-edge',
    playbook_name: "Quarantine the attacker's ingress route",
    action_type: 'edge_restriction',
    target_type: 'relationship',
    target_id: 'external-user-01--api-gateway-01',
    required_approval_tier: 'automatic_candidate',
    reversibility: 'reversible',
    operational_impact: 'low',
    security_gain_evidence: {
      attack_paths_before: 1,
      attack_paths_after: 0,
      top_attack_path_score_before: 0.8,
      top_attack_path_score_after: 0,
      critical_targets_reachable_before: 1,
      critical_targets_reachable_after: 0,
      blast_radius_reachable_before: 6,
      blast_radius_reachable_after: 0,
      blast_radius_critical_before: 2,
      blast_radius_critical_after: 0,
      security_gain: 30,
    },
    utility_score: {
      security_gain: 30,
      critical_asset_protection: 20,
      blast_radius_reduction: 12,
      evidence_quality: 14,
      reversibility_bonus: 5,
      operational_impact_penalty: 2,
      total: 78.9,
    },
    policy_pass: true,
    policy_failed_ids: [],
    recommended: true,
    changed_node_ids: [],
    changed_edge_ids: ['external-user-01--api-gateway-01'],
    synthetic: true,
    ...overrides,
  }
}

export function comparison(candidates: CandidatePlanAssessment[]): PlanComparisonResult {
  return {
    simulation_run_id: 'run-1',
    model_id: 'model-1',
    incident_candidate_id: 'inc-1',
    through_sequence_number: 12,
    autonomy_mode: 'autonomous',
    candidates,
    recommended_recommendation_id:
      candidates.find((item) => item.recommended)?.recommendation_id ?? null,
    decision_confidence: null,
    synthetic: true,
  }
}

export function orchestration(
  state: string,
  overrides: Partial<Orchestration> = {},
): Orchestration {
  return {
    orchestration_id: 'orch-1',
    simulation_run_id: 'run-1',
    model_id: 'model-1',
    incident_candidate_id: 'inc-1',
    through_sequence_number: 12,
    orchestration_version: 'v2',
    current_state: state,
    selected_recommendation_id: 'rec-1',
    required_approval_tier: 'automatic_candidate',
    created_by: 'Demo',
    created_at: '2026-07-21T09:00:00Z',
    updated_at: '2026-07-21T09:00:00Z',
    plan_steps: [],
    decisions: [],
    approvals: [],
    executions: [],
    verifications: [],
    rollback: null,
    synthetic: true,
    ...overrides,
  }
}

export const execution = {
  execution_id: 'x-1',
  plan_step_id: 's-1',
  playbook_id: 'quarantine-synthetic-ingress-edge',
  target_type: 'relationship',
  target_id: 'external-user-01--api-gateway-01',
  execution_state: 'completed_simulated',
  started_at: '2026-07-21T09:00:00Z',
  completed_at: '2026-07-21T09:00:00Z',
  mutation_summary: {},
  changed_node_ids: [],
  changed_edge_ids: ['external-user-01--api-gateway-01'],
  simulated_failure_reason: null,
  reversible: true,
  synthetic: true as const,
}

export const verification = {
  verification_id: 'v-1',
  execution_id: 'x-1',
  verification_status: 'successful_simulation',
  metrics: {},
  unintended_effects: [],
  started_at: '2026-07-21T09:00:00Z',
  completed_at: '2026-07-21T09:00:00Z',
  synthetic: true as const,
}

export function result(
  mode: string,
  candidates: CandidatePlanAssessment[] | null,
  orchestrationRecord: Orchestration | null,
): WorkflowRunResult {
  return {
    comparison: candidates ? comparison(candidates) : null,
    orchestration: orchestrationRecord,
    autonomy_mode: mode,
    auto_executed: false,
    auto_verified: false,
    stopped_reason: '',
    synthetic: true,
  }
}

export function inputs(overrides: Partial<StageInputs> = {}): StageInputs {
  return {
    run,
    scenarioName: 'Staged Cloud Compromise Demonstration',
    starting: false,
    playbackState: 'completed',
    currentEventIndex: 12,
    totalEventCount: 12,
    detectionEnabled: true,
    scoringStatus: 'ready',
    assessments: [assessment(1, false), assessment(5, true), assessment(9, true)],
    correlationEnabled: true,
    correlationStatus: 'ready',
    incident,
    predictionEnabled: true,
    predictionStatus: 'ready',
    prediction: snapshot(2),
    autonomyMode: 'autonomous',
    workflowStatus: 'idle',
    workflowError: null,
    result: null,
    orchestration: null,
    audit: null,
    ...overrides,
  }
}
