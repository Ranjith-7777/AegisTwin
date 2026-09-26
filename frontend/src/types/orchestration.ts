export interface PlanStep {
  plan_step_id: string
  step_number: number
  playbook_id: string
  recommendation_id: string
  target_type: string
  target_id: string
  required_approval_tier: string
  reversibility: string
  rationale: string
  expected_mutation: Record<string, unknown>
  current_status: string
  synthetic: true
}
export interface AgentDecision {
  agent_decision_id: string
  agent_name: string
  agent_version: string
  decision_type: string
  input_reference_ids: string[]
  output_summary: string
  decision: string
  ranking_score: number | null
  rationale: string
  warnings: string[]
  next_agent: string | null
  created_at: string
  synthetic: true
}
export interface ApprovalRequest {
  approval_request_id: string
  plan_step_id: string | null
  required_role: 'analyst' | 'administrator'
  approval_state: string
  requested_at: string
  decided_at: string | null
  decided_by: string | null
  decision_reason: string | null
  synthetic: true
}
export interface SyntheticExecution {
  execution_id: string
  plan_step_id: string
  playbook_id: string
  target_type: string
  target_id: string
  execution_state: string
  started_at: string
  completed_at: string | null
  mutation_summary: Record<string, unknown>
  changed_node_ids: string[]
  changed_edge_ids: string[]
  simulated_failure_reason: string | null
  reversible: boolean
  synthetic: true
}
export interface Verification {
  verification_id: string
  execution_id: string
  verification_status: string
  metrics: Record<string, unknown>
  unintended_effects: string[]
  started_at: string
  completed_at: string
  synthetic: true
}
export interface Rollback {
  rollback_id: string
  execution_id: string
  reason: string
  requested_by: string
  state: string
  restored_state_reference: string | null
  verification_summary: Record<string, unknown>
  synthetic: true
}
export interface Orchestration {
  orchestration_id: string
  simulation_run_id: string
  model_id: string
  incident_candidate_id: string
  through_sequence_number: number
  orchestration_version: string
  current_state: string
  selected_recommendation_id: string
  required_approval_tier: string
  created_by: string
  created_at: string
  updated_at: string
  plan_steps: PlanStep[]
  decisions: AgentDecision[]
  approvals: ApprovalRequest[]
  executions: SyntheticExecution[]
  verifications: Verification[]
  rollback: Rollback | null
  synthetic: true
}
export interface AuditEvent {
  audit_event_id: string
  sequence_number: number
  event_type: string
  actor_type: string
  actor_id: string
  actor_display_name: string
  previous_event_hash: string
  event_hash: string
  canonical_payload: Record<string, unknown>
  created_at: string
  synthetic: true
}
export interface AuditIntegrity {
  valid: boolean
  event_count: number
  first_invalid_sequence: number | null
  algorithm: string
  synthetic: true
}
