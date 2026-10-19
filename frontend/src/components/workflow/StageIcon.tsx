import {
  Ban,
  Check,
  CircleDot,
  Hand,
  LoaderCircle,
  Minus,
  RotateCcw,
  TriangleAlert,
  X,
} from 'lucide-react'

import type { StageStatus } from '../../lib/workflowStages'

export function StageIcon({ status }: { status: StageStatus }) {
  const Icon = {
    waiting: CircleDot,
    running: LoaderCircle,
    completed: Check,
    warning: TriangleAlert,
    awaiting: Hand,
    blocked: Ban,
    failed: X,
    rolled_back: RotateCcw,
    skipped: Minus,
  }[status]
  return (
    <span className="stage-icon" aria-hidden="true">
      <Icon strokeWidth={2.6} />
    </span>
  )
}
