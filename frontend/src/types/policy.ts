export type PolicyResult = 'pass' | 'fail' | 'not_applicable'

export interface PolicyDefinition {
  policy_id: string
  name: string
  purpose: string
  applies_to: string
  decision_effect: string
  enabled: boolean
  synthetic: true
}

export interface PolicyEvaluation {
  policy_id: string
  policy_name: string
  result: PolicyResult
  reason: string
  synthetic: true
}

export interface PolicyEvaluationResult {
  evaluations: PolicyEvaluation[]
  overall_pass: boolean
  failed_policy_ids: string[]
  synthetic: true
}
