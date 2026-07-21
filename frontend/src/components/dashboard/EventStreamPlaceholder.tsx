import { Radio } from 'lucide-react'

import { sampleEvents } from '../../mocks/eventStream'
import { SeverityBadge } from '../common/SeverityBadge'
import { Card, CardContent, CardHeader } from '../ui/card'

export function EventStreamPlaceholder() {
  return (
    <Card>
      <CardHeader>
        <div>
          <p className="eyebrow">Simulated sample data</p>
          <h2 className="panel-title">Live Event Stream</h2>
        </div>
        <Radio className="size-5 text-cyan-400" />
      </CardHeader>
      <CardContent className="space-y-3">
        {sampleEvents.map((event) => (
          <article className="event-item" key={event.id}>
            <div className="flex items-center justify-between gap-2">
              <span className="technical text-xs text-slate-500">
                {event.time} · {event.id}
              </span>
              <SeverityBadge severity={event.severity} />
            </div>
            <p className="mt-2 text-sm text-slate-300">{event.message}</p>
            <p className="mt-1 text-xs text-slate-600">Simulated sample — not a detected event</p>
          </article>
        ))}
      </CardContent>
    </Card>
  )
}
