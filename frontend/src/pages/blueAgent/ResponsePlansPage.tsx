import { GitBranch, Play, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Bar, KeyValue, Panel } from '../../components/ui/panel'
import { DefenseScoreBreakdown } from '../../components/response/DefenseScoreBreakdown'
import { useOptionalAutonomyWorkflow } from '../../hooks/useAutonomyWorkflow'
import { explainSelection } from '../../lib/decision'
import { humanize } from '../../lib/orchestrationState'
import { cn } from '../../lib/utils'
import { compareResponsePlans } from '../../services/bluePlanningApi'
import { createOrchestration } from '../../services/orchestrationApi'
import { analyzeResponses } from '../../services/responseApi'
import type { CandidatePlanAssessment, PlanComparisonResult } from '../../types/bluePlanning'
import type { ResponseRecommendation } from '../../types/response'
import { IncidentContextSelector } from './IncidentContextSelector'
import { useBlueAgentSelection } from './useBlueAgentSelection'
import { WhatIfDigitalTwin } from './WhatIfDigitalTwin'

function Delta({ before, after }: { before: number; after: number }) {
  return (
    <span
      className={cn('mono', after < before ? 'text-[var(--ok-text)]' : 'text-[var(--text-dim)]')}
    >
      {before}→{after}
    </span>
  )
}

/**
 * Candidate responses vs the selected response. Ranking uses the Response
 * Utility Score - a deterministic plan-ranking score computed from real
 * what-if recomputation on a cloned twin, never a learned probability.
 */
export function ResponsePlansPage() {
  const selection = useBlueAgentSelection()
  const workflow = useOptionalAutonomyWorkflow()
  const navigate = useNavigate()
  const [manual, setManual] = useState<PlanComparisonResult | null>(null)
  const [recommendations, setRecommendations] = useState<ResponseRecommendation[]>([])
  const [inspectedId, setInspectedId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Without an explicit URL context, show the live Blue workflow's comparison.
  const live = workflow?.result?.comparison ?? null
  const usingLive = !selection.runId && !manual && live !== null
  const result = manual ?? (usingLive ? live : null)
  const canCompare = Boolean(selection.runId && selection.modelId && selection.candidateId)

  useEffect(() => {
    if (!usingLive) return
    let cancelled = false
    void analyzeResponses({
      runId: live.simulation_run_id,
      modelId: live.model_id,
      throughSequence: live.through_sequence_number,
      predictionEnabled: true,
      topK: 5,
    })
      .then((analysis) => {
        if (!cancelled) setRecommendations(analysis.recommendations)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [live, usingLive])

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
      setManual(comparison)
      setRecommendations(analysis.recommendations)
      setInspectedId(null)
    } catch (reason) {
      setManual(null)
      setRecommendations([])
      setError(reason instanceof Error ? reason.message : 'Synthetic plan comparison failed.')
    } finally {
      setBusy(false)
    }
  }

  async function orchestrate(candidate: CandidatePlanAssessment) {
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
      void workflow?.refresh()
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

  const ranked = useMemo(
    () =>
      result
        ? [...result.candidates].sort(
            (left, right) =>
              Number(right.recommended) - Number(left.recommended) ||
              right.utility_score.total - left.utility_score.total,
          )
        : [],
    [result],
  )
  const selected = ranked.find((item) => item.recommended) ?? null
  const inspected =
    ranked.find((item) => item.recommendation_id === inspectedId) ?? selected ?? ranked[0] ?? null
  const explanation = result ? explainSelection(result.candidates) : null
  const inspectedRecommendation = recommendations.find(
    (item) => item.recommendation_id === inspected?.recommendation_id,
  )
  const maxUtility = Math.max(1, ...ranked.map((item) => item.utility_score.total))

  return (
    <section className="page-stack" aria-labelledby="response-plans-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Defence · Response Plans</p>
          <h1 id="response-plans-title">Response Plan Comparison</h1>
          <p>
            Candidates are ranked by the Response Utility Score - a deterministic plan-ranking
            score, not a machine-learning probability - from real Attack Graph / Blast Radius
            what-if recomputation on a hypothetical copy of the Digital Twin. The real twin is never
            mutated by this comparison.
          </p>
        </div>
        {usingLive ? (
          <Badge tone="accent" dot className="shrink-0">
            Live run context
          </Badge>
        ) : null}
      </header>
      <details className="panel" open={!usingLive}>
        <summary className="panel-head cursor-pointer list-none">
          <span className="panel-title">Incident context</span>
          <span className="text-[0.74rem] text-[var(--text-faint)]">
            {usingLive
              ? `Live: run ${live.simulation_run_id.slice(0, 8)} · seq ${String(live.through_sequence_number)} - choose another run to compare manually`
              : 'Choose run, model, incident and sequence'}
          </span>
        </summary>
        <div className="panel-body grid gap-3">
          <IncidentContextSelector {...selection} />
          <div>
            <Button disabled={!canCompare || busy} onClick={() => void compare()}>
              <GitBranch /> {busy ? 'Comparing candidate plans…' : 'Compare Candidate Plans'}
            </Button>
          </div>
        </div>
      </details>
      {error ? (
        <p role="alert" className="error-state">
          {error}
        </p>
      ) : null}
      {selection.loadError ? <p role="alert">{selection.loadError}</p> : null}
      {!result && !error ? (
        <Panel>
          <p className="m-0 text-[0.82rem] text-[var(--text-dim)]">
            No response plan comparison yet. Run a scenario (the Blue workflow fills this in
            automatically) or choose a run, model, incident and sequence above, then compare
            candidate plans.
          </p>
        </Panel>
      ) : null}
      {result ? (
        <>
          <div className="split-main">
            <Panel
              title="Selected response"
              icon={<Sparkles className="size-4" />}
              actions={
                selected ? (
                  <Badge tone="accent">Recommended plan</Badge>
                ) : (
                  <Badge tone="danger">None</Badge>
                )
              }
            >
              {selected && explanation ? (
                <div className="grid gap-3">
                  <div>
                    <p className="m-0 text-[1rem] font-semibold text-[var(--text)]">
                      {selected.playbook_name}
                    </p>
                    <p className="m-0 text-[0.75rem] text-[var(--text-faint)]">
                      {humanize(selected.action_type)} · {humanize(selected.target_type)}{' '}
                      <span className="mono">{selected.target_id}</span>
                    </p>
                  </div>
                  <div className="why-panel">
                    <strong>Why this action? </strong>
                    {explanation.headline}
                    <ul className="why-list">
                      {explanation.reasons.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : (
                <p className="m-0 text-[0.8rem] text-[var(--text-dim)]">
                  No candidate passed every applicable policy, so nothing is recommended.
                </p>
              )}
            </Panel>
            <Panel title="Decision confidence">
              {result.decision_confidence ? (
                <div className="grid gap-2">
                  <p className="m-0 text-[1.6rem] font-semibold text-[var(--text)]">
                    {result.decision_confidence.total.toFixed(1)}
                    <span className="text-[0.8rem] font-normal text-[var(--text-faint)]">
                      {' '}
                      / 100
                    </span>
                  </p>
                  <p className="m-0 text-[0.72rem] text-[var(--text-faint)]">
                    {result.decision_confidence.note}
                  </p>
                  <KeyValue
                    rows={[
                      ['Anomaly evidence', result.decision_confidence.anomaly_evidence.toFixed(1)],
                      [
                        'Incident coherence',
                        result.decision_confidence.incident_coherence.toFixed(1),
                      ],
                      [
                        'Technique diversity',
                        result.decision_confidence.technique_diversity.toFixed(1),
                      ],
                      [
                        'Attack-path corroboration',
                        result.decision_confidence.attack_path_corroboration.toFixed(1),
                      ],
                      [
                        'Simulation improvement',
                        result.decision_confidence.response_simulation_improvement.toFixed(1),
                      ],
                    ]}
                  />
                </div>
              ) : (
                <p className="m-0 text-[0.8rem] text-[var(--text-faint)]">
                  No candidate evidence is available for this incident yet.
                </p>
              )}
            </Panel>
          </div>

          <Panel title="Candidate responses" flush>
            <div className="table-wrap" aria-label="Candidate response plans">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Candidate</th>
                    <th>Response Utility Score</th>
                    <th className="num">Defense</th>
                    <th className="num">Attack paths</th>
                    <th className="num">Critical reach</th>
                    <th className="num">Blast radius</th>
                    <th>Twin changes</th>
                    <th>Impact · reversibility</th>
                    <th>Policy</th>
                    <th>Approval</th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.map((candidate) => {
                    const evidence = candidate.security_gain_evidence
                    const defense = recommendations.find(
                      (item) => item.recommendation_id === candidate.recommendation_id,
                    )?.defense_score
                    return (
                      <tr
                        key={candidate.recommendation_id}
                        className={cn(
                          'candidate-row cursor-pointer',
                          candidate.recommended && 'is-recommended',
                          inspected?.recommendation_id === candidate.recommendation_id &&
                            'is-selected',
                        )}
                        onClick={() => {
                          setInspectedId(candidate.recommendation_id)
                        }}
                      >
                        <td className="is-primary">
                          {candidate.playbook_name}
                          <span className="block text-[0.7rem] text-[var(--text-faint)]">
                            {candidate.target_id}
                          </span>
                        </td>
                        <td>
                          <div className="score-bar">
                            <Bar value={candidate.utility_score.total / maxUtility} />
                            <span className="mono">{candidate.utility_score.total.toFixed(1)}</span>
                          </div>
                        </td>
                        <td className="num">{defense?.toFixed(2) ?? '—'}</td>
                        <td className="num">
                          <Delta
                            before={evidence.attack_paths_before}
                            after={evidence.attack_paths_after}
                          />
                        </td>
                        <td className="num">
                          <Delta
                            before={evidence.critical_targets_reachable_before}
                            after={evidence.critical_targets_reachable_after}
                          />
                        </td>
                        <td className="num">
                          <Delta
                            before={evidence.blast_radius_reachable_before}
                            after={evidence.blast_radius_reachable_after}
                          />
                        </td>
                        <td>
                          {candidate.changed_node_ids.length} node ·{' '}
                          {candidate.changed_edge_ids.length} link
                        </td>
                        <td>
                          {candidate.operational_impact} · {candidate.reversibility}
                        </td>
                        <td>
                          <Badge tone={candidate.policy_pass ? 'ok' : 'danger'}>
                            {candidate.policy_pass
                              ? 'pass'
                              : candidate.policy_failed_ids.join(', ')}
                          </Badge>
                        </td>
                        <td>{humanize(candidate.required_approval_tier)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Panel>

          {inspected ? (
            <div className="split-2">
              <Panel
                title={`${inspected.playbook_name} · utility breakdown`}
                actions={
                  <Button
                    size="sm"
                    disabled={!inspected.policy_pass || busy}
                    title={
                      inspected.policy_pass
                        ? undefined
                        : 'Blocked by policy - cannot be orchestrated.'
                    }
                    onClick={() => void orchestrate(inspected)}
                  >
                    <Play /> Create Synthetic Response Orchestration
                  </Button>
                }
              >
                <KeyValue
                  rows={[
                    ['Security gain', inspected.utility_score.security_gain.toFixed(1)],
                    [
                      'Critical asset protection',
                      inspected.utility_score.critical_asset_protection.toFixed(1),
                    ],
                    [
                      'Blast radius reduction',
                      inspected.utility_score.blast_radius_reduction.toFixed(1),
                    ],
                    ['Evidence quality', inspected.utility_score.evidence_quality.toFixed(1)],
                    ['Reversibility bonus', inspected.utility_score.reversibility_bonus.toFixed(1)],
                    [
                      'Operational impact penalty',
                      `-${inspected.utility_score.operational_impact_penalty.toFixed(1)}`,
                    ],
                    ['Response Utility Score', inspected.utility_score.total.toFixed(1)],
                  ]}
                />
                {inspectedRecommendation ? (
                  <DefenseScoreBreakdown recommendation={inspectedRecommendation} />
                ) : null}
              </Panel>
              <Panel title="What-if Digital Twin">
                <WhatIfDigitalTwin key={inspected.recommendation_id} candidate={inspected} />
              </Panel>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  )
}
