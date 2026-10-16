import { Bot, Check, Play, RotateCcw, ShieldCheck, X } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useAutonomyWorkflow } from '../../hooks/useAutonomyWorkflow'
import { explainSelection } from '../../lib/decision'
import { humanize, orchestrationState } from '../../lib/orchestrationState'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Panel } from '../ui/panel'
import { useDecisionActions } from './useDecisionActions'

function Delta({ before, after, label }: { before: number; after: number; label: string }) {
  const better = after < before
  return (
    <div className="metric">
      <span className="metric-label">{label}</span>
      <span className={`metric-value is-sm ${better ? 'tone-ok' : ''}`}>
        {before} → {after}
      </span>
    </div>
  )
}

/**
 * The Blue Agent's current decision: selected playbook, the measured reason
 * it was chosen, the policy/approval gate, the execution state, and the
 * human-gate actions permitted for the caller's role.
 */
export function BlueDecisionPanel({ className }: { className?: string }) {
  const workflow = useAutonomyWorkflow()
  const { result, orchestration, session, autonomy, status, actionPending } = workflow
  const actions = useDecisionActions()
  const comparison = result?.comparison ?? null
  const selected = actions.selected
  const explanation = comparison ? explainSelection(comparison.candidates) : null
  const state = orchestrationState(orchestration?.current_state)
  const pending = actions.pending
  const { canApprove, canRollback, open: openDialog } = actions
  const canRun = workflow.canRun && (session?.can_operate ?? false)

  return (
    <Panel
      aria-label="Blue Agent decision"
      className={className}
      title="Blue Agent decision"
      icon={<Bot className="size-4" />}
      scroll
      actions={
        orchestration ? (
          <Badge tone={state.tone} dot>
            {state.label}
          </Badge>
        ) : null
      }
    >
      {!comparison ? (
        <div className="grid gap-2 text-[0.8rem] text-[var(--text-dim)]">
          {autonomy?.mode === 'observe' ? (
            <p className="m-0">
              Observe mode: the Blue Agent analyses evidence only and does not generate response
              plans. Switch mode on the Autonomous Workflow page to let it respond.
            </p>
          ) : status === 'running' ? (
            <p className="m-0 flex items-center gap-2">
              <span className="spinner" aria-hidden="true" /> Ranking candidate playbooks and
              simulating each on a cloned twin…
            </p>
          ) : workflow.canRun ? (
            <>
              <p className="m-0">
                An incident is correlated. Run the Blue workflow to rank responses and apply the
                current autonomy policy
                {workflow.autoRun ? ' - it starts automatically when the replay completes.' : '.'}
              </p>
              <div>
                <Button
                  size="sm"
                  onClick={() => void workflow.runWorkflow()}
                  disabled={!canRun}
                  title={canRun ? undefined : 'Requires the ANALYST role or higher.'}
                >
                  <Play /> Run Blue workflow
                </Button>
              </div>
            </>
          ) : (
            <p className="m-0">
              Waiting for a correlated incident. Start a scenario from the{' '}
              <Link to="/red-agent" className="card-link">
                Red Agent lab
              </Link>
              .
            </p>
          )}
          {workflow.error ? (
            <p className="m-0 text-[var(--danger-text)]" role="alert">
              {workflow.error}
            </p>
          ) : null}
        </div>
      ) : !selected ? (
        <div className="notice is-warn">
          <ShieldCheck className="size-4" />
          <span>
            {comparison.candidates.length} candidate plans were simulated, but none passed every
            applicable policy - nothing was recommended.
          </span>
        </div>
      ) : (
        <div className="grid gap-3">
          <div>
            <p className="eyebrow">Selected playbook</p>
            <p className="m-0 mt-0.5 text-[0.95rem] font-semibold text-[var(--text)]">
              {selected.playbook_name}
            </p>
            <p className="m-0 text-[0.75rem] text-[var(--text-faint)]">
              {humanize(selected.action_type)} · target{' '}
              <span className="mono">{selected.target_id}</span>
            </p>
          </div>
          <div className={pending ? 'notice is-warn btn-row' : 'btn-row'}>
            {pending ? (
              <>
                <Button
                  size="sm"
                  variant="success"
                  disabled={!canApprove || actionPending !== null}
                  title={canApprove ? undefined : `Requires the ${pending.required_role} role.`}
                  onClick={() => {
                    openDialog('approve')
                  }}
                >
                  <Check /> Approve & execute
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  disabled={!canApprove || actionPending !== null}
                  onClick={() => {
                    openDialog('reject')
                  }}
                >
                  <X /> Reject
                </Button>
              </>
            ) : null}
            {orchestration?.current_state === 'approved' ? (
              <Button
                size="sm"
                disabled={!(session?.can_operate ?? false) || actionPending !== null}
                onClick={() => void workflow.executeApproved()}
              >
                <Play /> Execute & verify
              </Button>
            ) : null}
            {orchestration &&
            ['verified', 'rollback_recommended'].includes(orchestration.current_state) &&
            !orchestration.rollback ? (
              <Button
                size="sm"
                variant="outline"
                disabled={!canRollback || actionPending !== null}
                title={canRollback ? undefined : 'Rollback requires the ADMIN role.'}
                onClick={() => {
                  openDialog('rollback')
                }}
              >
                <RotateCcw /> Roll back
              </Button>
            ) : null}
            {actionPending ? (
              <span className="flex items-center gap-2 text-[0.75rem] text-[var(--text-faint)]">
                <span className="spinner" aria-hidden="true" />
                {actionPending}…
              </span>
            ) : null}
          </div>
          {workflow.error ? (
            <p className="m-0 text-[0.78rem] text-[var(--danger-text)]" role="alert">
              {workflow.error}
            </p>
          ) : null}
          <div className="grid grid-cols-3 gap-3">
            <div className="metric">
              <span className="metric-label">Utility</span>
              <span className="metric-value is-sm tone-accent">
                {selected.utility_score.total.toFixed(1)}
              </span>
            </div>
            <Delta
              label="Attack paths"
              before={selected.security_gain_evidence.attack_paths_before}
              after={selected.security_gain_evidence.attack_paths_after}
            />
            <Delta
              label="Critical reach"
              before={selected.security_gain_evidence.critical_targets_reachable_before}
              after={selected.security_gain_evidence.critical_targets_reachable_after}
            />
          </div>
          {explanation ? (
            <div className="why-panel">
              <strong>Why this action? </strong>
              {explanation.headline}
              <ul className="why-list">
                {explanation.reasons.slice(1).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="flex flex-wrap gap-1.5">
            <Badge tone={selected.policy_pass ? 'ok' : 'danger'}>
              {selected.policy_pass ? 'Policy passed' : 'Policy failed'}
            </Badge>
            <Badge tone="neutral">{humanize(selected.required_approval_tier)}</Badge>
            <Badge tone="neutral">{selected.reversibility}</Badge>
            {comparison.decision_confidence ? (
              <Badge
                tone="neutral"
                title={comparison.decision_confidence.note}
              >{`Evidence quality ${comparison.decision_confidence.total.toFixed(0)}/100`}</Badge>
            ) : null}
          </div>
          {result?.stopped_reason ? (
            <p className="m-0 text-[0.75rem] text-[var(--text-faint)]">{result.stopped_reason}</p>
          ) : null}
        </div>
      )}
      {actions.element}
    </Panel>
  )
}
