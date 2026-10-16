import { useContext } from 'react'

import {
  AutonomyWorkflowContext,
  type AutonomyWorkflowContextValue,
} from '../app/autonomyWorkflowContext'

export function useAutonomyWorkflow(): AutonomyWorkflowContextValue {
  const value = useContext(AutonomyWorkflowContext)
  if (!value) throw new Error('useAutonomyWorkflow must be used inside AutonomyWorkflowProvider')
  return value
}

/** Non-throwing variant for components rendered both inside and outside the provider. */
export function useOptionalAutonomyWorkflow(): AutonomyWorkflowContextValue | null {
  return useContext(AutonomyWorkflowContext)
}
