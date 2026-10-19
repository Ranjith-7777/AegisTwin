import { Bot } from 'lucide-react'

import { autonomyLabel } from '../../lib/autonomy'
import type { AutonomyMode } from '../../types/autonomy'
import { cn } from '../../lib/utils'

export function AutonomyModePill({ mode }: { mode: AutonomyMode }) {
  return (
    <span
      className={cn(
        'mode-pill',
        mode === 'autonomous' && 'is-autonomous',
        mode === 'observe' && 'is-observe',
      )}
      title="Current Blue Agent autonomy mode"
    >
      <Bot className="size-3" aria-hidden="true" />
      {autonomyLabel(mode)}
    </span>
  )
}
