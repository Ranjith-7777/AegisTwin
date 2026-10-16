import type { CandidatePlanAssessment } from '../types/bluePlanning'

/**
 * Builds the "Why this action?" explanation from the deterministic scoring
 * data the backend returned for each candidate plan (what-if evidence,
 * response utility breakdown, policy outcome). It only restates those
 * numbers in words - it never adds reasoning the engine did not perform.
 */

export interface SelectionExplanation {
  headline: string
  reasons: string[]
  runnerUp: CandidatePlanAssessment | null
}

function target(candidate: CandidatePlanAssessment): string {
  return candidate.target_type === 'relationship'
    ? `the ${candidate.target_id.replace('--', ' → ')} link`
    : candidate.target_id
}

function count(value: number, word: string) {
  return `${String(value)} ${word}${value === 1 ? '' : 's'}`
}

/** The single most important measured effect of a candidate, in words. */
export function primaryEffect(candidate: CandidatePlanAssessment): string {
  const evidence = candidate.security_gain_evidence
  if (evidence.critical_targets_reachable_after < evidence.critical_targets_reachable_before) {
    return `cuts attacker reach to critical targets from ${String(evidence.critical_targets_reachable_before)} to ${String(evidence.critical_targets_reachable_after)}`
  }
  if (evidence.attack_paths_after < evidence.attack_paths_before) {
    return `reduces scored attack paths from ${String(evidence.attack_paths_before)} to ${String(evidence.attack_paths_after)}`
  }
  if (evidence.blast_radius_reachable_after < evidence.blast_radius_reachable_before) {
    return `shrinks the blast radius from ${count(evidence.blast_radius_reachable_before, 'reachable asset')} to ${String(evidence.blast_radius_reachable_after)}`
  }
  return 'adds defensive coverage without changing measured reachability'
}

export function explainSelection(
  candidates: CandidatePlanAssessment[],
): SelectionExplanation | null {
  const selected = candidates.find((item) => item.recommended)
  if (!selected) return null
  const others = candidates
    .filter((item) => item.recommendation_id !== selected.recommendation_id)
    .sort((left, right) => right.utility_score.total - left.utility_score.total)
  const runnerUp = others[0] ?? null
  const evidence = selected.security_gain_evidence
  const reasons: string[] = []

  reasons.push(
    `What-if simulation on a cloned twin: attack paths ${String(evidence.attack_paths_before)} → ${String(evidence.attack_paths_after)}, critical targets reachable ${String(evidence.critical_targets_reachable_before)} → ${String(evidence.critical_targets_reachable_after)}, blast radius ${String(evidence.blast_radius_reachable_before)} → ${String(evidence.blast_radius_reachable_after)}.`,
  )
  if (runnerUp) {
    const runnerEvidence = runnerUp.security_gain_evidence
    const sameEffect =
      runnerEvidence.attack_paths_after === evidence.attack_paths_after &&
      runnerEvidence.critical_targets_reachable_after === evidence.critical_targets_reachable_after
    const impactRank = { low: 0, medium: 1, high: 2 } as Record<string, number>
    const lessDisruptive =
      (impactRank[selected.operational_impact] ?? 1) <
      (impactRank[runnerUp.operational_impact] ?? 1)
    if (!runnerUp.policy_pass && selected.policy_pass) {
      reasons.push(
        `The next-highest candidate, ${runnerUp.playbook_name}, fails policy ${runnerUp.policy_failed_ids.join(', ')}.`,
      )
    } else if (sameEffect && lessDisruptive) {
      reasons.push(
        `${runnerUp.playbook_name} achieves the same containment but with ${runnerUp.operational_impact} operational impact versus ${selected.operational_impact}.`,
      )
    } else {
      reasons.push(
        `Response utility ${selected.utility_score.total.toFixed(1)} vs ${runnerUp.utility_score.total.toFixed(1)} for the next-best plan (${runnerUp.playbook_name}), which ${primaryEffect(runnerUp)}.`,
      )
    }
  }
  reasons.push(
    `${selected.operational_impact[0]?.toUpperCase() ?? ''}${selected.operational_impact.slice(1)} operational impact · ${selected.reversibility} · ${selected.policy_pass ? 'passes every applicable policy' : `fails ${selected.policy_failed_ids.join(', ')}`}.`,
  )
  if (selected.changed_edge_ids.length > 0) {
    reasons.push(
      `Would change ${count(selected.changed_edge_ids.length, 'relationship')} and ${count(selected.changed_node_ids.length, 'node')} in the twin.`,
    )
  }
  return {
    headline: `${selected.playbook_name} on ${target(selected)} was selected because it ${primaryEffect(selected)}.`,
    reasons,
    runnerUp,
  }
}
