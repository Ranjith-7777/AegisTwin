import { ArrowRight, Database, Laptop, Server, ShieldCheck } from 'lucide-react'

import { Card, CardContent, CardHeader } from '../ui/card'

const nodes = [
  { label: 'Employee Device', icon: Laptop },
  { label: 'Authentication Server', icon: ShieldCheck },
  { label: 'Application Server', icon: Server },
  { label: 'Critical Database', icon: Database },
]

export function DigitalTwinPlaceholder() {
  return (
    <Card className="xl:col-span-2">
      <CardHeader>
        <div>
          <p className="eyebrow">Infrastructure model</p>
          <h2 className="panel-title">Cyber Digital Twin</h2>
        </div>
        <span className="phase-label">Phase 5</span>
      </CardHeader>
      <CardContent>
        <div className="topology-placeholder" aria-label="Illustrative infrastructure topology">
          {nodes.map(({ label, icon: Icon }, index) => (
            <div className="contents" key={label}>
              <div className="topology-node">
                <Icon className="size-5" aria-hidden="true" />
                <span>{label}</span>
              </div>
              {index < nodes.length - 1 ? (
                <ArrowRight className="topology-arrow" aria-hidden="true" />
              ) : null}
            </div>
          ))}
        </div>
        <p className="mt-4 text-sm text-slate-500">
          Interactive topology arrives in Phase 5. This diagram is illustrative only.
        </p>
      </CardContent>
    </Card>
  )
}
