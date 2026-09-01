import type { ResponseRecommendation } from '../../types/response'

const PARTS = [
  { key: 'security_improvement', label: 'Security improvement', sign: '+' },
  { key: 'service_disruption', label: 'Service disruption', sign: '−' },
  { key: 'resource_cost', label: 'Resource cost', sign: '−' },
  { key: 'sla_penalty', label: 'SLA penalty', sign: '−' },
] as const

/**
 * Defense Score = Security Improvement − Service Disruption − Resource Cost − SLA Penalty.
 */
export function DefenseScoreBreakdown({
  recommendation,
}: {
  recommendation: ResponseRecommendation
}) {
  const components = recommendation.defense_components
  return (
    <div className="defense-score" aria-label="Defense score breakdown">
      <div className="defense-score-head">
        <span className="eyebrow">Defense Score</span>
        <strong>{recommendation.defense_score.toFixed(3)}</strong>
      </div>
      <dl className="defense-score-parts">
        {PARTS.map((part) => (
          <div key={part.key} className={`defense-part is-${part.sign === '+' ? 'gain' : 'cost'}`}>
            <dt>{part.label}</dt>
            <dd>
              {part.sign}
              {components[part.key].toFixed(3)}
            </dd>
          </div>
        ))}
      </dl>
      <p className="defense-score-explanation">{recommendation.defense_explanation}</p>
    </div>
  )
}
