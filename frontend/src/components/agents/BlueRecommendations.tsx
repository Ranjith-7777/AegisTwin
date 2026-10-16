import {
  ArrowRight,
  Check,
  ChevronDown,
  Eye,
  Network,
  Play,
  ShieldCheck,
  ShieldOff,
  UserX,
} from 'lucide-react'
import { useState, type ReactElement } from 'react'
import { Link } from 'react-router-dom'

import { useAutonomyWorkflow } from '../../hooks/useAutonomyWorkflow'
import { explainSelection, primaryEffect } from '../../lib/decision'
import { humanize, orchestrationState } from '../../lib/orchestrationState'
import type { CandidatePlanAssessment } from '../../types/bluePlanning'
import { Button } from '../ui/button'
import { useDecisionActions } from '../workflow/useDecisionActions'

function actionIcon(actionType: string): ReactElement {
  if (actionType.includes('edge') || actionType.includes('network')) return <Network />
  if (actionType.includes('identity') || actionType.includes('credential')) return <UserX />
  if (actionType.includes('observe') || actionType.includes('telemetry')) return <Eye />
  if (actionType.includes('isolat') || actionType.includes('quarantine')) return <ShieldOff />
  return <ShieldCheck />
}

const UTILITY_PARTS: { key: keyof CandidatePlanAssessment['utility_score']; label: string }[] = [
  { key: 'security_gain', label: 'Security gain' },
  { key: 'critical_asset_protection', label: 'Critical protection' },
  { key: 'blast_radius_reduction', label: 'Blast radius' },
  { key: 'evidence_quality', label: 'Evidence quality' },
  { key: 'reversibility_bonus', label: 'Reversibility' },
  { key: 'operational_impact_penalty', label: 'Impact penalty' },
]

/**
 * Every candidate the Blue Agent simulated, ranked, with the human gate on
 * the selected plan and an expandable, number-backed explanation per row.
 */
export function BlueRecommendations() {
  const workflow = useAutonomyWorkflow()
  const actions = useDecisionActions()
  const [open, setOpen] = useState<string | null>(null)
  const comparison = workflow.result?.comparison ?? null
  const explanation = comparison ? explainSelection(comparison.candidates) : null
  const ranked = comparison
    ? [...comparison.candidates].sort(
        (left, right) =>
          Number(right.recommended) - Number(left.recommended) ||
          right.utility_score.total - left.utility_score.total,
      )
    : []
  const state = workflow.orchestration
    ? orchestrationState(workflow.orchestration.current_state)
    : null

  function control(candidate: CandidatePlanAssessment) {
    if (!candidate.recommended) return <span className="rec-status">Not selected</span>
    if (actions.pending)
      return (
        <Button
          size="sm"
          variant="soft"
          disabled={!actions.canApprove || actions.busy}
          title={actions.canApprove ? 'Approve, then execute and verify' : 'Requires ADMIN'}
          onClick={() => {
            actions.open('approve')
          }}
        >
          <Check /> Approve
        </Button>
      )
    if (actions.canExecuteApproved)
      return (
        <Button
          size="sm"
          variant="soft"
          disabled={!actions.canOperate || actions.busy}
          onClick={actions.executeApproved}
        >
          <Play /> Execute
        </Button>
      )
    return (
      <span className={`state-pill tone-${state?.tone ?? 'accent'}`}>
        {state?.label ?? 'Selected'}
      </span>
    )
  }

  return (
    <section className="panel" aria-label="Blue Agent recommendations">
      <header className="panel-head">
        <div>
          <h2 className="panel-title">Blue Agent Recommendations</h2>
          <p className="panel-subtitle">Ranked by response utility</p>
        </div>
        <Link className="card-link" to="/blue-agent/response-plans">
          View all <ArrowRight className="size-3.5" />
        </Link>
      </header>
      <div className="panel-body is-scroll">
        {ranked.length ? (
          <ul className="bluerec-list">
            {ranked.map((candidate) => {
              const expanded = open === candidate.recommendation_id
              return (
                <li key={candidate.recommendation_id}>
                  <div className="bluerec-row">
                    <span
                      className={`bluerec-icon${candidate.recommended ? ' is-selected' : ''}`}
                      aria-hidden="true"
                    >
                      {actionIcon(candidate.action_type)}
                    </span>
                    <span className="min-w-0">
                      <p className="rec-name" title={candidate.playbook_name}>
                        {candidate.playbook_name}
                      </p>
                      <p className="rec-target">
                        {humanize(candidate.action_type)} · {candidate.target_id}
                      </p>
                    </span>
                    <span className={`sev sev-${candidate.operational_impact}`}>
                      {candidate.operational_impact}
                    </span>
                    {control(candidate)}
                    <button
                      type="button"
                      className="expand-btn"
                      aria-expanded={expanded}
                      aria-label={`${expanded ? 'Hide' : 'Show'} details for ${candidate.playbook_name}`}
                      onClick={() => {
                        setOpen(expanded ? null : candidate.recommendation_id)
                      }}
                    >
                      <ChevronDown aria-hidden="true" />
                    </button>
                  </div>
                  {expanded ? (
                    <div className="bluerec-detail">
                      {candidate.recommended && explanation ? (
                        <div className="why-panel">
                          <strong>Why this action? </strong>
                          {explanation.headline}
                          <ul className="why-list">
                            {explanation.reasons.slice(1).map((reason) => (
                              <li key={reason}>{reason}</li>
                            ))}
                          </ul>
                        </div>
                      ) : (
                        <p className="m-0">
                          This plan {primaryEffect(candidate)}.{' '}
                          {candidate.policy_pass
                            ? 'It passes policy but ranked below the selected plan.'
                            : `It fails policy ${candidate.policy_failed_ids.join(', ')}.`}
                        </p>
                      )}
                      <div className="grid grid-cols-3 gap-x-3 gap-y-1">
                        {UTILITY_PARTS.map((part) => (
                          <span key={part.key} className="flex justify-between gap-2">
                            <span className="text-[var(--text-faint)]">{part.label}</span>
                            <span className="mono text-[var(--text)]">
                              {candidate.utility_score[part.key].toFixed(1)}
                            </span>
                          </span>
                        ))}
                      </div>
                      <p className="m-0">
                        Utility <strong>{candidate.utility_score.total.toFixed(1)}</strong> ·{' '}
                        {humanize(candidate.required_approval_tier)} · {candidate.reversibility}
                      </p>
                    </div>
                  ) : null}
                </li>
              )
            })}
          </ul>
        ) : (
          <div className="empty-state">
            <ShieldCheck className="size-6" />
            <span>
              {workflow.status === 'running'
                ? 'Ranking candidate playbooks…'
                : workflow.autonomy?.mode === 'observe'
                  ? 'Observe mode generates no response plans.'
                  : 'Candidates appear once the Blue workflow runs for a correlated incident.'}
            </span>
          </div>
        )}
      </div>
      {actions.element}
    </section>
  )
}
