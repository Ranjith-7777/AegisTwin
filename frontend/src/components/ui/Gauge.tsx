interface GaugeProps {
  value: number
  max?: number
  label: string
  tone: 'healthy' | 'warn' | 'danger' | 'info'
  valueLabel?: string
}

const toneColor: Record<GaugeProps['tone'], string> = {
  healthy: 'var(--state-ok)',
  warn: 'var(--state-degraded)',
  danger: 'var(--state-attack)',
  info: 'var(--state-healthy)',
}

/**
 * A simple, static semicircular gauge. No animation beyond the CSS
 * transition on the arc when `value` changes — deliberately restrained
 * per the Phase 2 design rules (no glow, no looping motion).
 */
export function Gauge({ value, max = 100, label, tone, valueLabel }: GaugeProps) {
  const clamped = Math.min(max, Math.max(0, value))
  const fraction = max > 0 ? clamped / max : 0
  const radius = 70
  const circumference = Math.PI * radius
  const offset = circumference * (1 - fraction)
  const color = toneColor[tone]

  return (
    <div className="gauge" role="img" aria-label={`${label}: ${valueLabel ?? String(clamped)}`}>
      <svg viewBox="0 0 176 100" className="gauge-svg">
        <path
          d="M 18 92 A 70 70 0 0 1 158 92"
          fill="none"
          stroke="var(--border)"
          strokeWidth="14"
          strokeLinecap="round"
        />
        <path
          d="M 18 92 A 70 70 0 0 1 158 92"
          fill="none"
          stroke={color}
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="gauge-arc"
        />
      </svg>
      <div className="gauge-readout">
        <span className="gauge-value">{valueLabel ?? clamped}</span>
        <span className="gauge-label">{label}</span>
      </div>
    </div>
  )
}
