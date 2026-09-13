import { Link } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'

import type { IncidentCandidate } from '../../types/correlation'

const stateLabel: Record<string, string> = {
  monitoring: 'Monitoring',
  correlated: 'Correlated',
  high_priority: 'High priority',
  closed: 'Closed',
}

/** Command Centre's incident summary: real evidence only, no fabricated fields. */
export function ActiveIncidentCard({ incident }: { incident: IncidentCandidate | null }) {
  return (
    <section className="card" aria-label="Active incident">
      <div className="card-head">
        <h2 className="card-title">
          <ShieldAlert className="size-4 shrink-0" aria-hidden="true" />
          Active Incident
        </h2>
        {incident ? (
          <Link className="card-link" to="/incidents">
            View incident
          </Link>
        ) : null}
      </div>
      <div className="p-4">
        {incident ? (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <div className="col-span-2">
              <span className="chip chip-danger">
                <span className="chip-dot" aria-hidden="true" />
                {stateLabel[incident.correlation_state] ?? incident.correlation_state}
              </span>
            </div>
            <dt className="text-slate-500">Priority</dt>
            <dd className="capitalize text-slate-900">{incident.priority}</dd>
            <dt className="text-slate-500">Detected at sequence</dt>
            <dd className="text-slate-900">{incident.first_sequence_number}</dd>
            <dt className="text-slate-500">Evidence items</dt>
            <dd className="text-slate-900">{incident.evidence_count}</dd>
            <dt className="text-slate-500">MITRE techniques</dt>
            <dd className="text-slate-900">{incident.observed_technique_ids.length}</dd>
            <dt className="text-slate-500">Affected assets</dt>
            <dd className="text-slate-900">{incident.involved_asset_ids.length}</dd>
          </dl>
        ) : (
          <div className="blue-empty">
            <p>No active incidents. Correlated evidence will appear here once detected.</p>
          </div>
        )}
      </div>
    </section>
  )
}
