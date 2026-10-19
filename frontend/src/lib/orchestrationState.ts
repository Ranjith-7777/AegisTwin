import type { BadgeTone } from '../components/ui/badge'

/** Display label and tone for each backend orchestration state. */
export const ORCHESTRATION_STATE: Record<string, { label: string; tone: BadgeTone }> = {
  planning: { label: 'Planning', tone: 'accent' },
  policy_review: { label: 'Policy review', tone: 'accent' },
  simulation_validation: { label: 'Simulation stale', tone: 'warn' },
  rejected: { label: 'Blocked / rejected', tone: 'danger' },
  awaiting_analyst_approval: { label: 'Awaiting analyst approval', tone: 'warn' },
  awaiting_administrator_approval: { label: 'Awaiting administrator approval', tone: 'warn' },
  approved: { label: 'Approved', tone: 'accent' },
  synthetic_execution_completed: { label: 'Executed (synthetic)', tone: 'accent' },
  synthetic_execution_failed: { label: 'Execution failed', tone: 'danger' },
  verified: { label: 'Verified', tone: 'ok' },
  rollback_recommended: { label: 'Rollback recommended', tone: 'warn' },
  synthetic_rollback_completed: { label: 'Rolled back', tone: 'predicted' },
}

export function orchestrationState(state: string | null | undefined) {
  if (!state) return { label: 'Not started', tone: 'neutral' as BadgeTone }
  return ORCHESTRATION_STATE[state] ?? { label: state.replaceAll('_', ' '), tone: 'neutral' }
}

export function humanize(value: string): string {
  return value.replaceAll('_', ' ').replaceAll('-', ' ')
}
