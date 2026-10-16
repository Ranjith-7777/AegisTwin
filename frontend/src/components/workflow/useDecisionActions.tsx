import { useState } from 'react'

import { useAutonomyWorkflow } from '../../hooks/useAutonomyWorkflow'
import { Button } from '../ui/button'
import { Dialog } from '../ui/Dialog'

export type DecisionKind = 'approve' | 'reject' | 'rollback'

const DEFAULT_REASON: Record<DecisionKind, string> = {
  approve: 'Evidence and what-if simulation reviewed; approving synthetic execution.',
  reject: 'Rejected after review of the proposed synthetic action.',
  rollback: 'Operator-requested synthetic rollback to restore the prior twin state.',
}

/**
 * The human gates on the Blue Agent's selected plan, shared by every card that
 * offers them. Permissions mirror the backend: approval decisions and
 * rollback are ADMIN-gated, execution needs the operator (ANALYST) role. Every
 * decision is captured with a reason that is written to the audit chain.
 */
export function useDecisionActions() {
  const workflow = useAutonomyWorkflow()
  const { result, orchestration, session, actionPending } = workflow
  const [dialog, setDialog] = useState<DecisionKind | null>(null)
  const [reason, setReason] = useState('')
  const selected = result?.comparison?.candidates.find((item) => item.recommended) ?? null
  const pending = orchestration?.approvals.find((item) => item.approval_state === 'pending') ?? null
  const canApprove = session?.can_administer ?? false
  const canRollback = session?.can_administer ?? false
  const canOperate = session?.can_operate ?? false
  const busy = actionPending !== null
  const canExecuteApproved = orchestration?.current_state === 'approved'
  const rollbackAvailable =
    orchestration !== null &&
    ['verified', 'rollback_recommended'].includes(orchestration.current_state) &&
    !orchestration.rollback

  function open(kind: DecisionKind) {
    setReason(DEFAULT_REASON[kind])
    setDialog(kind)
  }

  function submit() {
    const text = reason.trim()
    if (text.length < 3 || !dialog) return
    const action = dialog
    setDialog(null)
    if (action === 'approve') void workflow.approve(text)
    if (action === 'reject') void workflow.reject(text)
    if (action === 'rollback') void workflow.rollback(text)
  }

  const element = (
    <Dialog
      open={dialog !== null}
      title={
        dialog === 'approve'
          ? 'Approve synthetic execution'
          : dialog === 'reject'
            ? 'Reject the proposed action'
            : 'Roll back the synthetic execution'
      }
      onClose={() => {
        setDialog(null)
      }}
      footer={
        <>
          <Button
            variant="outline"
            onClick={() => {
              setDialog(null)
            }}
          >
            Cancel
          </Button>
          <Button
            variant={dialog === 'reject' ? 'danger' : dialog === 'rollback' ? 'default' : 'success'}
            disabled={reason.trim().length < 3}
            onClick={submit}
          >
            Confirm
          </Button>
        </>
      }
    >
      {dialog === 'approve' && selected ? (
        <p className="m-0">
          Approve <strong>{selected.playbook_name}</strong> on{' '}
          <span className="mono">{selected.target_id}</span>. The action executes against the
          synthetic twin only and is then independently verified.
        </p>
      ) : null}
      {dialog === 'rollback' ? (
        <p className="m-0">
          Restores the twin state captured before the synthetic execution. No real system is
          affected.
        </p>
      ) : null}
      <label className="field">
        <span>Decision reason (recorded in the audit chain)</span>
        <textarea
          rows={3}
          value={reason}
          onChange={(event) => {
            setReason(event.target.value)
          }}
        />
      </label>
    </Dialog>
  )

  return {
    selected,
    pending,
    canApprove,
    canRollback,
    canOperate,
    busy,
    canExecuteApproved,
    rollbackAvailable,
    open,
    executeApproved: () => void workflow.executeApproved(),
    element,
  }
}
