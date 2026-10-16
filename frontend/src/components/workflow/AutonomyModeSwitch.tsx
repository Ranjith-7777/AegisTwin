import { useState } from 'react'

import { useAutonomyWorkflow } from '../../hooks/useAutonomyWorkflow'
import { AUTONOMY_MODES } from '../../lib/autonomy'
import type { AutonomyMode } from '../../types/autonomy'
import { cn } from '../../lib/utils'
import { Button } from '../ui/button'
import { Dialog } from '../ui/Dialog'

/**
 * Segmented control for the backend autonomy mode. Raising the mode to
 * Autonomous requires an explicit confirmation, mirroring the backend's
 * `confirm=true` requirement - it is a deliberate choice, never a default.
 */
export function AutonomyModeSwitch({ compact = false }: { compact?: boolean }) {
  const { autonomy, autonomyUpdating, setAutonomyMode, session } = useAutonomyWorkflow()
  const [confirming, setConfirming] = useState(false)
  const current = autonomy?.mode ?? null
  const canChange = session?.can_operate ?? false
  function choose(mode: AutonomyMode) {
    if (mode === current) return
    if (mode === 'autonomous') setConfirming(true)
    else void setAutonomyMode(mode)
  }
  return (
    <>
      <div className="mode-switch" role="radiogroup" aria-label="Blue Agent autonomy mode">
        {AUTONOMY_MODES.map((item) => (
          <button
            key={item.mode}
            type="button"
            role="radio"
            aria-checked={current === item.mode}
            className={cn('mode-option', current === item.mode && 'is-active')}
            disabled={!canChange || autonomyUpdating}
            title={canChange ? item.description : 'Requires the ANALYST role or higher.'}
            onClick={() => {
              choose(item.mode)
            }}
          >
            <strong>{item.label}</strong>
            {compact ? null : <span>{item.short}</span>}
          </button>
        ))}
      </div>
      <Dialog
        open={confirming}
        title="Enable autonomous mode?"
        onClose={() => {
          setConfirming(false)
        }}
        footer={
          <>
            <Button
              variant="outline"
              onClick={() => {
                setConfirming(false)
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                setConfirming(false)
                void setAutonomyMode('autonomous')
              }}
            >
              Enable autonomous mode
            </Button>
          </>
        }
      >
        <p className="m-0">
          The Blue Agent will execute and verify a response <strong>automatically</strong> when the
          selected playbook is low-impact, reversible, automatic-eligible and passes every policy
          (POL-001..006). Anything else still waits for a human approval.
        </p>
        <p className="m-0 text-[var(--text-faint)]">
          All execution is synthetic: it changes the Digital Twin state only, never real
          infrastructure.
        </p>
      </Dialog>
    </>
  )
}
