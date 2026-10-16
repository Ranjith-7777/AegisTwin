import { createContext } from 'react'

import type { WorkflowStage, RailStep, WorkflowStatus } from '../lib/workflowStages'
import type { AutonomyConfig, AutonomyMode } from '../types/autonomy'
import type { AuditIntegrity, Orchestration } from '../types/orchestration'
import type { SessionView } from '../types/session'
import type { WorkflowRunResult } from '../types/workflow'

export interface AutonomyWorkflowContextValue {
  session: SessionView | null
  autonomy: AutonomyConfig | null
  autonomyUpdating: boolean
  setAutonomyMode: (mode: AutonomyMode) => Promise<void>
  /** Run the Blue workflow automatically once the attack replay completes. */
  autoRun: boolean
  setAutoRun: (value: boolean) => void
  status: WorkflowStatus
  error: string | null
  result: WorkflowRunResult | null
  orchestration: Orchestration | null
  audit: AuditIntegrity | null
  stages: WorkflowStage[]
  rail: RailStep[]
  /** True when a run, model and incident exist so the Blue workflow can run. */
  canRun: boolean
  actionPending: string | null
  runWorkflow: () => Promise<void>
  approve: (reason: string) => Promise<void>
  reject: (reason: string) => Promise<void>
  executeApproved: () => Promise<void>
  verify: () => Promise<void>
  rollback: (reason: string) => Promise<void>
  refresh: () => Promise<void>
}

export const AutonomyWorkflowContext = createContext<AutonomyWorkflowContextValue | null>(null)
