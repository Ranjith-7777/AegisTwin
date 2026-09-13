import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Button } from '../../components/ui/button'
import { Card, CardContent, CardHeader } from '../../components/ui/card'
import { Badge } from '../../components/ui/badge'
import { DefenseScoreBreakdown } from '../../components/response/DefenseScoreBreakdown'
import { compareResponsePlans } from '../../services/bluePlanningApi'
import { createOrchestration } from '../../services/orchestrationApi'
import { analyzeResponses } from '../../services/responseApi'
import type { CandidatePlanAssessment, PlanComparisonResult } from '../../types/bluePlanning'
import type { ResponseRecommendation } from '../../types/response'
import { IncidentContextSelector } from './IncidentContextSelector'
import { useBlueAgentSelection } from './useBlueAgentSelection'

function label(value: string) {
  return value.replaceAll('_', ' ')
}

function CandidateCard({
  candidate,
  recommendation,
  onSelect,
}: {
  candidate: CandidatePlanAssessment
  recommendation: ResponseRecommendation | undefined
  onSelect: () => void
}) {
  const evidence = candidate.security_gain_evidence
  return (
    <Card className={candidate.recommended ? 'border-blue-400 ring-1 ring-blue-200' : undefined}>
      <CardHeader>
        <div>
          <h3 className="font-semibold">{candidate.playbook_name}</h3>
          <p className="text-sm text-slate-600">
            {label(candidate.target_type)}: {candidate.target_id}
          </p>
        </div>
        {candidate.recommended ? (
          <Badge className="chip-accent">Recommended plan</Badge>
        ) : (
          <Badge className="chip-muted">Rank alternative</Badge>
        )}
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-bold">
          {candidate.utility_score.total.toFixed(1)}{' '}
          <span className="text-sm font-normal text-slate-500">Response Utility Score</span>
        </p>
        <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <dt>Security gain</dt>
          <dd>{candidate.utility_score.security_gain.toFixed(1)}</dd>
          <dt>Critical asset protection</dt>
          <dd>{candidate.utility_score.critical_asset_protection.toFixed(1)}</dd>
          <dt>Blast radius reduction</dt>
          <dd>{candidate.utility_score.blast_radius_reduction.toFixed(1)}</dd>
          <dt>Evidence quality</dt>
          <dd>{candidate.utility_score.evidence_quality.toFixed(1)}</dd>
          <dt>Reversibility bonus</dt>
          <dd>{candidate.utility_score.reversibility_bonus.toFixed(1)}</dd>
          <dt>Operational impact penalty</dt>
          <dd>-{candidate.utility_score.operational_impact_penalty.toFixed(1)}</dd>
        </dl>
        <h4 className="mt-3 font-semibold">What-if: before → simulated after</h4>
        <p className="text-sm">
          Attack paths: {evidence.attack_paths_before} → {evidence.attack_paths_after}
        </p>
        <p className="text-sm">
          Critical targets reachable: {evidence.critical_targets_reachable_before} →{' '}
          {evidence.critical_targets_reachable_after}
        </p>
        <p className="text-sm">
          Blast radius reachable: {evidence.blast_radius_reachable_before} →{' '}
          {evidence.blast_radius_reachable_after}
        </p>
        <p className="mt-2 text-sm">
          Approval: {label(candidate.required_approval_tier)} · {label(candidate.reversibility)} ·{' '}
          {label(candidate.operational_impact)} impact
        </p>
        <p className="mt-1 text-sm">
          Policy:{' '}
          {candidate.policy_pass ? 'pass' : `fail (${candidate.policy_failed_ids.join(', ')})`}
        </p>
        {recommendation ? (
          <details className="mt-3">
            <summary className="cursor-pointer text-sm font-semibold">
              Existing Blue Agent Defense Score (distinct signal, feeds evidence quality above)
            </summary>
            <DefenseScoreBreakdown recommendation={recommendation} />
          </details>
        ) : null}
        <div className="mt-3">
          <Button
            disabled={!candidate.policy_pass}
            onClick={onSelect}
            title={
              candidate.policy_pass ? undefined : 'Blocked by policy - cannot be orchestrated.'
            }
          >
            Create Synthetic Response Orchestration
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function ResponsePlansPage() {
  const selection = useBlueAgentSelection()
  const navigate = useNavigate()
  const [result, setResult] = useState<PlanComparisonResult | null>(null)
  const [recommendations, setRecommendations] = useState<ResponseRecommendation[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canCompare = Boolean(selection.runId && selection.modelId && selection.candidateId)

  async function compare() {
    if (!canCompare) return
    setBusy(true)
    setError(null)
    try {
      const [comparison, analysis] = await Promise.all([
        compareResponsePlans({
          runId: selection.runId,
          modelId: selection.modelId,
          incidentCandidateId: selection.candidateId,
          throughSequence: selection.sequence || 1,
          topK: 5,
        }),
        analyzeResponses({
          runId: selection.runId,
          modelId: selection.modelId,
          throughSequence: selection.sequence || 1,
          predictionEnabled: true,
          topK: 5,
        }),
      ])
      setResult(comparison)
      setRecommendations(analysis.recommendations)
    } catch (reason) {
      setResult(null)
      setRecommendations([])
      setError(reason instanceof Error ? reason.message : 'Synthetic plan comparison failed.')
    } finally {
      setBusy(false)
    }
  }

  async function select(candidate: CandidatePlanAssessment) {
    if (!result) return
    setBusy(true)
    setError(null)
    try {
      const orchestration = await createOrchestration(result.simulation_run_id, {
        model_id: result.model_id,
        incident_candidate_id: result.incident_candidate_id,
        selected_recommendation_id: candidate.recommendation_id,
        through_sequence_number: result.through_sequence_number,
      })
      selection.setOrchestrationId(orchestration.orchestration_id)
      void navigate({
        pathname: '/blue-agent/verification',
        search: new URLSearchParams({
          run: result.simulation_run_id,
          model: result.model_id,
          incident: result.incident_candidate_id,
          sequence: String(result.through_sequence_number),
          orchestration: orchestration.orchestration_id,
        }).toString(),
      })
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : 'Synthetic orchestration creation failed.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="space-y-6" aria-labelledby="response-plans-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Blue Agent · Response Plans</p>
          <h1 id="response-plans-title">Response Plan Comparison</h1>
          <p>
            Candidate plans are ranked by the Response Utility Score - a deterministic plan-ranking
            score, not a machine-learning probability - using real Attack Graph / Blast Radius
            what-if recomputation on a hypothetical copy of the Digital Twin. The real topology is
            never mutated by this comparison.
          </p>
        </div>
      </header>
      <IncidentContextSelector {...selection} />
      <div>
        <Button disabled={!canCompare || busy} onClick={() => void compare()}>
          {busy ? 'Comparing candidate plans…' : 'Compare Candidate Plans'}
        </Button>
      </div>
      {error ? (
        <p role="alert" className="text-red-700">
          {error}
        </p>
      ) : null}
      {selection.loadError ? <p role="alert">{selection.loadError}</p> : null}
      {!result && !error ? (
        <Card>
          <CardContent>
            <p>
              No response plan comparison selected. Choose a run, model, incident and sequence
              above, then compare candidate plans.
            </p>
          </CardContent>
        </Card>
      ) : null}
      {result ? (
        <>
          <Card>
            <CardHeader>
              <h2 className="panel-title">Decision Confidence</h2>
            </CardHeader>
            <CardContent>
              {result.decision_confidence ? (
                <>
                  <p className="text-2xl font-bold">
                    {result.decision_confidence.total.toFixed(1)}
                  </p>
                  <p className="text-sm text-slate-600">{result.decision_confidence.note}</p>
                  <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
                    <dt>Anomaly evidence</dt>
                    <dd>{result.decision_confidence.anomaly_evidence.toFixed(1)}</dd>
                    <dt>Incident coherence</dt>
                    <dd>{result.decision_confidence.incident_coherence.toFixed(1)}</dd>
                    <dt>Technique diversity</dt>
                    <dd>{result.decision_confidence.technique_diversity.toFixed(1)}</dd>
                    <dt>Attack path corroboration</dt>
                    <dd>{result.decision_confidence.attack_path_corroboration.toFixed(1)}</dd>
                    <dt>Response simulation improvement</dt>
                    <dd>{result.decision_confidence.response_simulation_improvement.toFixed(1)}</dd>
                  </dl>
                </>
              ) : (
                <p>No candidate evidence is available for this incident yet.</p>
              )}
            </CardContent>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2" aria-label="Candidate response plans">
            {result.candidates.map((candidate) => (
              <CandidateCard
                key={candidate.recommendation_id}
                candidate={candidate}
                recommendation={recommendations.find(
                  (item) => item.recommendation_id === candidate.recommendation_id,
                )}
                onSelect={() => void select(candidate)}
              />
            ))}
          </div>
        </>
      ) : null}
    </section>
  )
}
