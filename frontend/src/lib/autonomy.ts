import type { AutonomyMode } from '../types/autonomy'

/**
 * Plain-language descriptions of the backend autonomy modes
 * (backend/app/schemas/autonomy.py). The agents are deterministic and
 * policy-governed - no language model or learned policy is involved.
 */
export const AUTONOMY_MODES: {
  mode: AutonomyMode
  label: string
  short: string
  description: string
}[] = [
  {
    mode: 'observe',
    label: 'Observe',
    short: 'Detect & analyse only',
    description: 'Detection, correlation and prediction run; no response plan is generated.',
  },
  {
    mode: 'recommend',
    label: 'Recommend',
    short: 'Suggest defensive actions',
    description: 'Candidate plans are simulated and ranked, but never orchestrated or executed.',
  },
  {
    mode: 'approval_required',
    label: 'Approval required',
    short: 'Human approves execution',
    description:
      'The selected plan is validated against policy and prepared; a human approval is required before synthetic execution.',
  },
  {
    mode: 'autonomous',
    label: 'Autonomous',
    short: 'Policy-governed loop',
    description:
      'Low-impact, reversible, policy-passing playbooks execute and verify automatically; anything else still waits for approval.',
  },
]

export function autonomyLabel(mode: string | null | undefined): string {
  return AUTONOMY_MODES.find((item) => item.mode === mode)?.label ?? 'Unknown mode'
}
