import type { ReactNode } from 'react'

import { cn } from '../../lib/utils'

export type KpiTone = 'blue' | 'red' | 'green' | 'amber' | 'violet' | 'lavender'

/**
 * Compact KPI: icon tile, label, value and one line of context. The value is
 * always a real figure or an explicit "—"; the optional visual must be drawn
 * from a real series or composition, never decoration.
 */
export function KpiCard({
  icon,
  tone,
  label,
  value,
  unit,
  sub,
  visual,
  title,
}: {
  icon: ReactNode
  tone: KpiTone
  label: string
  value: ReactNode
  unit?: string
  sub: ReactNode
  visual?: ReactNode
  title?: string
}) {
  const empty = value === '—'
  return (
    <div className="kpi" title={title}>
      <span className={`kpi-icon is-${tone}`} aria-hidden="true">
        {icon}
      </span>
      <span className="kpi-body">
        <span className="kpi-label">{label}</span>
        <span className={cn('kpi-value', empty && 'is-empty')}>
          {value}
          {unit && !empty ? <small>{unit}</small> : null}
        </span>
        <span className="kpi-sub">{sub}</span>
      </span>
      {visual ?? <span />}
    </div>
  )
}

/** Bar sparkline of a real count series. Renders nothing for an empty series. */
export function Spark({
  values,
  tone,
  label,
}: {
  values: number[]
  tone: 'blue' | 'red' | 'green' | 'violet'
  label: string
}) {
  if (values.length === 0) return null
  const peak = Math.max(1, ...values)
  return (
    <span className={`spark is-${tone}`} role="img" aria-label={label}>
      {values.map((value, index) => (
        <span
          key={index}
          className={value === 0 ? 'is-muted' : undefined}
          style={{ height: `${String(Math.max(6, (value / peak) * 100))}%` }}
        />
      ))}
    </span>
  )
}

/**
 * Tiny labelled columns for a categorical breakdown (e.g. assets by
 * criticality). Heights are proportional to the real counts.
 */
export function MiniColumns({
  parts,
  label,
}: {
  parts: { key: string; label: string; value: number; color: string }[]
  label: string
}) {
  const peak = Math.max(1, ...parts.map((part) => part.value))
  if (parts.every((part) => part.value === 0)) return null
  return (
    <span
      className="mini-columns"
      role="img"
      aria-label={`${label}: ${parts.map((part) => `${String(part.value)} ${part.label}`).join(', ')}`}
    >
      {parts.map((part) => (
        <span key={part.key} className="mini-column" title={`${String(part.value)} ${part.label}`}>
          <span className="mini-column-track">
            <span
              style={{
                height: `${String(part.value === 0 ? 0 : Math.max(10, (part.value / peak) * 100))}%`,
                background: part.color,
              }}
            />
          </span>
          <span className="mini-column-key">{part.key}</span>
        </span>
      ))}
    </span>
  )
}
