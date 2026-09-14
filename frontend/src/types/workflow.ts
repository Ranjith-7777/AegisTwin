import type { PlanComparisonResult } from './bluePlanning'
import type { Orchestration } from './orchestration'

export interface WorkflowRunResult {
  /** null in OBSERVE mode - evidence only, no response plan is generated. */
  comparison: PlanComparisonResult | null
  orchestration: Orchestration | null
  autonomy_mode: string
  auto_executed: boolean
  auto_verified: boolean
  stopped_reason: string
  synthetic: true
}
