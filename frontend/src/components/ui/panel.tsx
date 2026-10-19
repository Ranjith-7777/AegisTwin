import type { HTMLAttributes, ReactNode } from 'react'

import { cn } from '../../lib/utils'

interface PanelProps extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
  title?: ReactNode
  icon?: ReactNode
  actions?: ReactNode
  footer?: ReactNode
  /** Scroll the body internally instead of growing the page. */
  scroll?: boolean
  flush?: boolean
  bodyClassName?: string
}

/** Standard bordered surface with an optional header row and footer. */
export function Panel({
  title,
  icon,
  actions,
  footer,
  scroll = false,
  flush = false,
  className,
  bodyClassName,
  children,
  ...props
}: PanelProps) {
  return (
    <section className={cn('panel', className)} {...props}>
      {title || actions ? (
        <header className="panel-head">
          {title ? (
            <h2 className="panel-title">
              {icon}
              {title}
            </h2>
          ) : (
            <span />
          )}
          {actions ? <div className="btn-row">{actions}</div> : null}
        </header>
      ) : null}
      <div className={cn('panel-body', scroll && 'is-scroll', flush && 'is-flush', bodyClassName)}>
        {children}
      </div>
      {footer ? <footer className="panel-foot">{footer}</footer> : null}
    </section>
  )
}

export function Metric({
  label,
  value,
  sub,
  tone,
  small = false,
  className,
}: {
  label: ReactNode
  value: ReactNode
  sub?: ReactNode
  tone?: 'ok' | 'warn' | 'danger' | 'accent'
  small?: boolean
  className?: string
}) {
  return (
    <div className={cn('metric', className)}>
      <span className="metric-label">{label}</span>
      <span
        className={cn(
          'metric-value',
          small && 'is-sm',
          value === '—' ? 'is-empty' : tone && `tone-${tone}`,
        )}
      >
        {value}
      </span>
      {sub ? <span className="metric-sub">{sub}</span> : null}
    </div>
  )
}

export function KeyValue({
  rows,
  left = false,
  className,
}: {
  rows: [ReactNode, ReactNode][]
  left?: boolean
  className?: string
}) {
  return (
    <dl className={cn('kv', left && 'is-left', className)}>
      {rows.map(([key, value], index) => (
        <div key={index} className="contents">
          <dt>{key}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  )
}

export function Bar({
  value,
  tone,
  label,
}: {
  /** 0..1 */
  value: number
  tone?: 'ok' | 'warn' | 'danger'
  label?: string
}) {
  const clamped = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0))
  return (
    <div
      className={cn('bar', tone && `tone-${tone}`)}
      role="meter"
      aria-valuemin={0}
      aria-valuemax={1}
      aria-valuenow={clamped}
      aria-label={label}
    >
      <span style={{ width: `${String(clamped * 100)}%` }} />
    </div>
  )
}

export function Tip({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <span className="tip" tabIndex={0}>
      {children}
      <span className="tip-bubble" role="tooltip">
        {label}
      </span>
    </span>
  )
}
