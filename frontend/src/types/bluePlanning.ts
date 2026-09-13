export interface SecurityGainEvidence {
  attack_paths_before: number
  attack_paths_after: number
  top_attack_path_score_before: number
  top_attack_path_score_after: number
  critical_targets_reachable_before: number
  critical_targets_reachable_after: number
  blast_radius_reachable_before: number
  blast_radius_reachable_after: number
  blast_radius_critical_before: number
  blast_radius_critical_after: number
  security_gain: number
}

export interface ResponseUtilityScoreBreakdown {
  security_gain: number
  critical_asset_protection: number
  blast_radius_reduction: number
  evidence_quality: number
  reversibility_bonus: number
  operational_impact_penalty: number
  total: number
}

export interface CandidatePlanAssessment {
  recommendation_id: string
  playbook_id: string
  playbook_name: string
  action_type: string
  target_type: string
  target_id: string
  required_approval_tier: string
  reversibility: string
  operational_impact: string
  security_gain_evidence: SecurityGainEvidence
  utility_score: ResponseUtilityScoreBreakdown
  policy_pass: boolean
  policy_failed_ids: string[]
  recommended: boolean
  synthetic: true
}

export interface DecisionConfidence {
  anomaly_evidence: number
  incident_coherence: number
  technique_diversity: number
  attack_path_corroboration: number
  response_simulation_improvement: number
  total: number
  note: string
  synthetic: true
}

export interface PlanComparisonResult {
  simulation_run_id: string
  model_id: string
  incident_candidate_id: string
  through_sequence_number: number
  autonomy_mode: string
  candidates: CandidatePlanAssessment[]
  recommended_recommendation_id: string | null
  decision_confidence: DecisionConfidence | null
  synthetic: true
}
