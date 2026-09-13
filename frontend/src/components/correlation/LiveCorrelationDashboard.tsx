import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { Badge } from '../ui/badge'
import { Card, CardContent, CardHeader } from '../ui/card'

const labels: Record<string, string> = {
  temporal_proximity: 'Temporal proximity',
  entity_continuity: 'Entity continuity',
  anomaly_evidence: 'Anomaly evidence',
  technique_diversity: 'Technique diversity',
  tactic_progression: 'Tactic progression',
  infrastructure_continuity: 'Infrastructure continuity',
}

export function LiveCorrelationDashboard() {
  const {
    currentIncidentCandidate: candidate,
    techniqueTimeline,
    events,
    assessmentsByEventId,
  } = useSimulationPlayback()
  return (
    <>
      <Card>
        <CardHeader>
          <div>
            <p className="eyebrow">Causal synthetic correlation</p>
            <h2 className="panel-title">Incident Candidate Summary</h2>
          </div>
          <Badge>Synthetic</Badge>
        </CardHeader>
        <CardContent aria-live="polite">
          {candidate ? (
            <div className="space-y-2 text-sm text-slate-600">
              <strong>{candidate.title}</strong>
              <p>
                {candidate.correlation_state} · priority {candidate.priority} · coherence score{' '}
                {candidate.correlation_score.toFixed(3)}
              </p>
              <p>
                {candidate.evidence_count} evidence items · sequence{' '}
                {candidate.first_sequence_number}–{candidate.latest_sequence_number}
              </p>
              <p>
                User: {candidate.primary_user_id ?? 'none'} · Device:{' '}
                {candidate.primary_device_id ?? 'none'}
              </p>
              <p>Assets: {candidate.involved_asset_ids.join(', ') || 'none'}</p>
              <p>Tactics: {candidate.observed_tactic_ids.join(', ') || 'none'}</p>
              <p>Techniques: {candidate.observed_technique_ids.join(', ') || 'none'}</p>
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              No incident candidate update has been streamed.
            </p>
          )}
          <p className="mt-4 text-xs text-amber-200">
            Correlation indicates related unusual synthetic activity. It does not confirm a real
            attack.
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <div>
            <p className="eyebrow">Observed techniques</p>
            <h2 className="panel-title">MITRE Timeline</h2>
          </div>
        </CardHeader>
        <CardContent>
          {techniqueTimeline.length ? (
            <ol className="space-y-3">
              {techniqueTimeline.map((item) => (
                <li
                  key={item.mapping_id}
                  className="border-l border-blue-200 pl-3 text-sm text-slate-600"
                >
                  <strong>
                    {item.technique_id} — {item.technique_name}
                  </strong>
                  <p>
                    {item.tactic} · confidence {item.mapping_confidence.toFixed(2)} (heuristic, not
                    probability)
                  </p>
                  <p className="text-xs text-slate-500">
                    Sequence {item.sequence_number}: {item.rationale}
                  </p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm text-slate-500">No technique observations streamed.</p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <div>
            <p className="eyebrow">Fixed weighted evidence</p>
            <h2 className="panel-title">Correlation Components</h2>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {Object.entries(labels).map(([key, label]) => (
            <div key={key}>
              <div className="flex justify-between text-xs text-slate-500">
                <span>{label}</span>
                <span>{(candidate?.component_scores[key] ?? 0).toFixed(3)}</span>
              </div>
              <progress max="1" value={candidate?.component_scores[key] ?? 0} className="w-full" />
            </div>
          ))}
          <p className="text-xs text-slate-500">
            Components measure evidence coherence, not attack probability.
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <div>
            <p className="eyebrow">Available through current sequence</p>
            <h2 className="panel-title">Evidence Trail</h2>
          </div>
        </CardHeader>
        <CardContent>
          {candidate ? (
            events
              .filter(
                (event) =>
                  assessmentsByEventId[event.event_id] ||
                  techniqueTimeline.some((item) => item.event_id === event.event_id),
              )
              .map((event) => (
                <p key={event.event_id} className="mb-2 text-xs text-slate-600">
                  {event.action} · {event.source_id} → {event.destination_id ?? 'none'} ·{' '}
                  {assessmentsByEventId[event.event_id]?.classification ?? 'mapped evidence'}
                </p>
              ))
          ) : (
            <p className="text-sm text-slate-500">
              Evidence appears causally as playback advances.
            </p>
          )}
        </CardContent>
      </Card>
    </>
  )
}
