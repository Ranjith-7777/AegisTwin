import { CircleCheck, RotateCcw, ShieldAlert, Sparkles } from 'lucide-react'

import type { SyntheticExecution } from '../../types/orchestration'

const STATES: { label: string; color: string; dashed?: boolean }[] = [
  { label: 'Nominal', color: '#22c55e' },
  { label: 'Anomalous', color: '#f59e0b' },
  { label: 'Incident evidence', color: '#ef4444' },
  { label: 'Predicted target', color: '#0891b2', dashed: true },
  { label: 'Mitigation proposed', color: '#7c3aed', dashed: true },
  { label: 'Mitigated (executed)', color: '#2563eb' },
  { label: 'Restored', color: '#16a34a' },
]

const LINES: { label: string; color: string; dashed?: boolean }[] = [
  { label: 'Attack / incident link', color: '#ef4444', dashed: true },
  { label: 'Proposed mitigation', color: '#7c3aed', dashed: true },
  { label: 'Normal relationship', color: '#a8b3c4' },
]

/** Key to the twin's node states and link styles. */
export function TwinLegend() {
  return (
    <div className="twin-legend" id="twin-legend" aria-label="Digital Twin legend">
      {STATES.map((item) => (
        <span key={item.label} className="legend-item" style={{ color: item.color }}>
          <span
            className={item.dashed ? 'legend-dot is-dashed' : 'legend-dot'}
            style={{ background: item.color }}
            aria-hidden="true"
          />
          <span className="text-[var(--text-dim)]">{item.label}</span>
        </span>
      ))}
      <hr />
      {LINES.map((item) => (
        <span key={item.label} className="legend-item" style={{ color: item.color }}>
          <span
            className={item.dashed ? 'legend-line is-dashed' : 'legend-line'}
            aria-hidden="true"
          />
          <span className="text-[var(--text-dim)]">{item.label}</span>
        </span>
      ))}
    </div>
  )
}

/**
 * One-line statement of what the twin is currently showing - executed and
 * proposed mitigations are named explicitly so they are never confused.
 */
export function TwinStateBanner({
  execution,
  proposedCount,
  attackActive,
  offset = false,
}: {
  execution: SyntheticExecution | null
  proposedCount: number
  attackActive: boolean
  /** Sit below a floating toolbar instead of at the top edge. */
  offset?: boolean
}) {
  if (execution?.execution_state === 'rolled_back_simulated') {
    return (
      <p className={`twin-banner is-rolled${offset ? ' is-offset' : ''}`} role="status">
        <RotateCcw className="size-3.5" aria-hidden="true" /> Mitigation rolled back - prior twin
        state restored
      </p>
    )
  }
  if (execution?.execution_state === 'completed_simulated') {
    return (
      <p className={`twin-banner is-executed${offset ? ' is-offset' : ''}`} role="status">
        <CircleCheck className="size-3.5" aria-hidden="true" /> Mitigation executed in the twin ·{' '}
        {execution.changed_node_ids.length} node(s), {execution.changed_edge_ids.length} link(s)
        changed
      </p>
    )
  }
  if (proposedCount > 0) {
    return (
      <p className={`twin-banner is-proposed${offset ? ' is-offset' : ''}`} role="status">
        <Sparkles className="size-3.5" aria-hidden="true" /> Proposed fix shown as dashed outline -
        what-if only, not executed
      </p>
    )
  }
  if (attackActive) {
    return (
      <p className={`twin-banner is-attack${offset ? ' is-offset' : ''}`} role="status">
        <ShieldAlert className="size-3.5" aria-hidden="true" /> Attack replay in progress
      </p>
    )
  }
  return null
}
