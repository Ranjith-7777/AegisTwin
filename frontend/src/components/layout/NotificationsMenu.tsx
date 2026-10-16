import { Bell, CircleAlert, Hand, ShieldAlert, ShieldX, Unplug } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

import { useOptionalAutonomyWorkflow } from '../../hooks/useAutonomyWorkflow'
import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { useSystemData } from '../../hooks/useSystemData'

interface Alert {
  id: string
  title: string
  detail: string
  to: string
  icon: ReactNode
  tone: 'danger' | 'warn' | 'accent'
}

/**
 * Operator alerts derived from live state only: a pending human approval,
 * a failed verification, a broken audit chain, a workflow error, an open
 * incident in the current run, or the backend being unreachable.
 */
export function NotificationsMenu() {
  const navigate = useNavigate()
  const { health } = useSystemData()
  const workflow = useOptionalAutonomyWorkflow()
  const playback = useSimulationPlayback()
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onPointer(event: PointerEvent) {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false)
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('pointerdown', onPointer)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('pointerdown', onPointer)
      window.removeEventListener('keydown', onKey)
    }
  }, [open])

  const alerts: Alert[] = []
  if (health && (health.status !== 'healthy' || health.database !== 'connected'))
    alerts.push({
      id: 'backend',
      title: 'Backend degraded',
      detail: `API ${health.status}, database ${health.database}.`,
      to: '/settings',
      icon: <Unplug aria-hidden="true" />,
      tone: 'danger',
    })
  if (workflow?.stages.some((stage) => stage.status === 'awaiting'))
    alerts.push({
      id: 'approval',
      title: 'Approval required',
      detail: 'A validated synthetic response is waiting for a human decision.',
      to: '/workflow',
      icon: <Hand aria-hidden="true" />,
      tone: 'warn',
    })
  const verification = workflow?.orchestration?.verifications[0]
  if (verification && verification.verification_status !== 'successful_simulation')
    alerts.push({
      id: 'verification',
      title: 'Verification did not meet objective',
      detail: 'The executed mitigation needs review or rollback.',
      to: '/blue-agent/verification',
      icon: <ShieldX aria-hidden="true" />,
      tone: 'danger',
    })
  if (workflow?.audit && !workflow.audit.valid)
    alerts.push({
      id: 'audit',
      title: 'Audit chain integrity failed',
      detail: `Chain broken at sequence ${String(workflow.audit.first_invalid_sequence ?? '?')}.`,
      to: '/audit-trail',
      icon: <CircleAlert aria-hidden="true" />,
      tone: 'danger',
    })
  if (workflow?.error)
    alerts.push({
      id: 'workflow-error',
      title: 'Workflow error',
      detail: workflow.error,
      to: '/workflow',
      icon: <CircleAlert aria-hidden="true" />,
      tone: 'danger',
    })
  const incident = playback.currentIncidentCandidate
  if (incident && !workflow?.orchestration?.verifications.length)
    alerts.push({
      id: 'incident',
      title: `${incident.priority} incident correlated`,
      detail: incident.title,
      to: '/incidents',
      icon: <ShieldAlert aria-hidden="true" />,
      tone: incident.priority === 'critical' || incident.priority === 'high' ? 'danger' : 'warn',
    })

  return (
    <div className="relative" ref={root}>
      <button
        type="button"
        className="icon-btn"
        aria-label={alerts.length ? `Alerts: ${String(alerts.length)}` : 'Alerts: none'}
        aria-expanded={open}
        aria-haspopup="true"
        onClick={() => {
          setOpen((value) => !value)
        }}
      >
        <Bell aria-hidden="true" />
        {alerts.length ? <span className="dot" aria-hidden="true" /> : null}
      </button>
      {open ? (
        <div className="popover w-[20rem]" role="menu" aria-label="Alerts">
          <p className="popover-title">Alerts</p>
          {alerts.length === 0 ? (
            <p className="m-0 px-3 pb-2.5 text-[0.8rem] text-[var(--text-faint)]">
              No alerts. The range is idle or every action is resolved.
            </p>
          ) : (
            alerts.map((alert) => (
              <button
                key={alert.id}
                type="button"
                role="menuitem"
                className="popover-item"
                onClick={() => {
                  setOpen(false)
                  void navigate(alert.to)
                }}
              >
                <span
                  className={`mt-0.5 [&_svg]:size-4 ${
                    alert.tone === 'danger'
                      ? 'text-[var(--danger)]'
                      : alert.tone === 'warn'
                        ? 'text-[var(--warn)]'
                        : 'text-[var(--accent)]'
                  }`}
                >
                  {alert.icon}
                </span>
                <span className="min-w-0 flex-1">
                  {alert.title}
                  <small>{alert.detail}</small>
                </span>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  )
}
