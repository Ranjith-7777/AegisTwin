import { Card, CardContent, CardHeader } from '../ui/card'

const stages = ['Initial access', 'Privilege escalation', 'Lateral movement', 'Collection attempt']

export function MitreTimelinePlaceholder() {
  return (
    <Card>
      <CardHeader>
        <div>
          <p className="eyebrow">Illustrative only</p>
          <h2 className="panel-title">MITRE ATT&CK Timeline</h2>
        </div>
        <span className="phase-label">Phase 5</span>
      </CardHeader>
      <CardContent>
        <ol className="timeline-placeholder">
          {stages.map((stage, index) => (
            <li key={stage}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <p>{stage}</p>
            </li>
          ))}
        </ol>
        <p className="mt-4 text-xs text-slate-500">
          Example stages only. AegisTwin has not detected these techniques.
        </p>
      </CardContent>
    </Card>
  )
}
