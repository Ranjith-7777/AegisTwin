import { Card, CardContent, CardHeader } from '../ui/card'
import type { PredictionHypothesis, PredictionSnapshot } from '../../types/prediction'

function label(item: PredictionHypothesis) {
  return (
    item.predicted_technique_id ??
    item.predicted_tactic ??
    item.predicted_asset_id ??
    item.predicted_objective ??
    'insufficient evidence'
  )
}

export function LivePredictionDashboard({
  current,
  timeline,
}: {
  current: PredictionSnapshot | null
  timeline: PredictionSnapshot[]
}) {
  const groups = (current?.hypotheses ?? []).reduce<Record<string, PredictionHypothesis[]>>(
    (result, item) => {
      const group = result[item.hypothesis_type] ?? []
      group.push(item)
      result[item.hypothesis_type] = group
      return result
    },
    {},
  )
  return (
    <Card>
      <CardHeader>
        <div>
          <p className="eyebrow">Causal synthetic hypotheses</p>
          <h2 className="panel-title">Next-stage prediction</h2>
        </div>
        <span className="status-chip">{current?.prediction_state ?? 'idle'}</span>
      </CardHeader>
      <CardContent className="space-y-4">
        {!current ? <p className="text-slate-500">No prediction snapshot received.</p> : null}
        {current ? (
          <>
            <p>
              Current estimate: <strong>{current.current_stage_estimate}</strong> ·{' '}
              {current.current_tactic_estimate} · through sequence {current.through_sequence_number}
            </p>
            {current.insufficient_evidence_reason ? (
              <p className="text-amber-200">{current.insufficient_evidence_reason}</p>
            ) : null}
            {Object.entries(groups).map(([kind, items]) => (
              <section key={kind}>
                <h3 className="font-semibold">{kind.replaceAll('_', ' ')}</h3>
                {items.map((item) => (
                  <article
                    key={item.hypothesis_id}
                    className="mt-2 rounded border border-slate-200 p-3"
                  >
                    <strong>
                      #{item.rank} {label(item)}
                    </strong>
                    <span className="ml-2 text-xs text-slate-500">
                      score {item.prediction_score.toFixed(3)}
                    </span>
                    <p className="text-sm text-slate-600">{item.rationale}</p>
                    <p className="text-xs text-slate-500">
                      Components:{' '}
                      {Object.entries(item.component_scores)
                        .map(([name, score]) => `${name} ${score.toFixed(2)}`)
                        .join(' · ')}
                    </p>
                    {item.contradictory_evidence.length ? (
                      <p className="text-xs text-amber-300">
                        Contradictions: {item.contradictory_evidence.join('; ')}
                      </p>
                    ) : null}
                  </article>
                ))}
              </section>
            ))}
            <p className="text-xs text-slate-500">
              Evolution:{' '}
              {timeline
                .map(
                  (item) =>
                    `${String(item.through_sequence_number)}:${item.current_stage_estimate}`,
                )
                .join(' → ')}
            </p>
            <p className="text-xs text-amber-200">
              Ranked hypotheses from local synthetic evidence—not probabilities, certainty, or a
              confirmed attack.
            </p>
          </>
        ) : null}
      </CardContent>
    </Card>
  )
}
