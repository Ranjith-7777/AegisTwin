import { ArrowUpRight, ShieldCheck } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { Button } from '../ui/button'
import type { ResponseRecommendation } from '../../types/response'

export function BlueAgentCard({
  recommendation,
  busy,
  ready,
  error,
  onAnalyze,
  onApprove,
}: {
  recommendation: ResponseRecommendation | null
  busy: boolean
  ready: boolean
  error: string | null
  onAnalyze: () => void
  onApprove: () => void
}) {
  const navigate = useNavigate()
  const components = recommendation?.defense_components
  const slaImpact = components ? components.sla_penalty + components.service_disruption : 0
  return (
    <section className="card blue-card" aria-label="Blue Agent recommendation">
      <div className="card-head">
        <h2 className="card-title">
          <ShieldCheck className="size-4 shrink-0" aria-hidden="true" />
          Blue Agent Recommendation
        </h2>
        {recommendation ? (
          <span className="chip chip-muted">Rank {recommendation.rank}</span>
        ) : null}
      </div>
      {recommendation && components ? (
        <div className="blue-body">
          <div className="blue-action">
            <p className="blue-action-name">{recommendation.playbook_name}</p>
            <p className="blue-action-target">
              {recommendation.target_type.replaceAll('_', ' ')} · {recommendation.target_id}
            </p>
          </div>
          <dl className="blue-metrics">
            <div className="blue-metric is-primary">
              <dt>Defense Score</dt>
              <dd>{recommendation.defense_score.toFixed(2)}</dd>
            </div>
            <div className="blue-metric is-gain">
              <dt>Security improvement</dt>
              <dd>+{components.security_improvement.toFixed(2)}</dd>
            </div>
            <div className="blue-metric is-cost">
              <dt>Availability / SLA impact</dt>
              <dd>−{slaImpact.toFixed(2)}</dd>
            </div>
            <div className="blue-metric">
              <dt>Approval required</dt>
              <dd>{recommendation.required_approval_tier.replaceAll('_', ' ')}</dd>
            </div>
          </dl>
          <div className="blue-actions">
            <Button size="sm" disabled={busy} onClick={onApprove}>
              Approve
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                void navigate('/response-centre')
              }}
            >
              View Details
              <ArrowUpRight className="size-4" />
            </Button>
          </div>
        </div>
      ) : (
        <div className="blue-empty">
          <p>
            {error ??
              (ready
                ? 'No mitigation has been ranked for the current sequence.'
                : 'Start a scenario with a detection model to rank mitigations.')}
          </p>
          <Button size="sm" variant="outline" disabled={!ready || busy} onClick={onAnalyze}>
            {busy ? 'Ranking…' : 'Rank mitigations'}
          </Button>
        </div>
      )}
    </section>
  )
}
