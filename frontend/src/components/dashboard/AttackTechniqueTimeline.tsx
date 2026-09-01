import { Link } from 'react-router-dom'

import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { Card, CardContent, CardHeader } from '../ui/card'

export function AttackTechniqueTimeline() {
  const { techniqueTimeline, currentIncidentCandidate } = useSimulationPlayback()
  return (
    <Card aria-label="Attack technique timeline">
      <CardHeader>
        <div>
          <p className="eyebrow">Observed synthetic evidence</p>
          <h2 className="panel-title">MITRE ATT&amp;CK Timeline</h2>
        </div>
        <Link className="text-sm text-cyan-300" to="/mitre">
          Open catalogue
        </Link>
      </CardHeader>
      <CardContent>
        {techniqueTimeline.length ? (
          <ol className="timeline-placeholder">
            {techniqueTimeline.map((item) => (
              <li key={item.mapping_id}>
                <span>{String(item.sequence_number).padStart(2, '0')}</span>
                <p>
                  <strong className="text-slate-200">{item.technique_id}</strong> ·{' '}
                  {item.technique_name}
                  <br />
                  <span className="agent-detail">
                    {item.tactic} · confidence {item.mapping_confidence.toFixed(2)}
                  </span>
                </p>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-slate-400">
            No ATT&amp;CK technique has been observed in the current replay. Techniques appear only
            when synthetic telemetry explicitly supports the mapping.
          </p>
        )}
        {currentIncidentCandidate ? (
          <p className="mt-4 text-xs text-amber-200">
            Correlated candidate state: {currentIncidentCandidate.correlation_state} · priority{' '}
            {currentIncidentCandidate.priority}. This is correlated evidence, not a confirmed
            attack.
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}
