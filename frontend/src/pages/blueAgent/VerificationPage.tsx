import { Check, Play, RotateCcw, ShieldCheck, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { KeyValue, Panel } from '../../components/ui/panel'
import { AutonomyModePill } from '../../components/workflow/AutonomyModePill'
import { useOptionalAutonomyWorkflow } from '../../hooks/useAutonomyWorkflow'
import { humanize, orchestrationState } from '../../lib/orchestrationState'
import { cn } from '../../lib/utils'
import {
  decideApproval,
  executeSynthetic,
  getOrchestration,
  listOrchestrations,
  rollbackSynthetic,
  verifySynthetic,
} from '../../services/orchestrationApi'
import type { Orchestration } from '../../types/orchestration'
import { useBlueAgentSelection } from './useBlueAgentSelection'

type StepState = 'done' | 'current' | 'failed' | 'rolled' | 'pending'

/** planned → approved → executed → verifying → verified (or failed → rolled back). */
function lifecycleOf(item: Orchestration): { label: string; state: StepState }[] {
  const approval = item.approvals[0]
  const execution = item.executions[0]
  const verification = item.verifications[0]
  const blocked = item.current_state === 'rejected'
  const approved =
    item.current_state === 'approved' ||
    Boolean(execution) ||
    approval?.approval_state === 'approved'
  const steps: { label: string; state: StepState }[] = [
    { label: 'Planned', state: 'done' },
    {
      label: blocked ? 'Rejected' : approval ? 'Human approval' : 'Auto-approval',
      state: blocked ? 'failed' : approved ? 'done' : 'current',
    },
    {
      label: 'Executed (synthetic)',
      state: execution
        ? execution.execution_state === 'failed_simulated'
          ? 'failed'
          : 'done'
        : approved
          ? 'current'
          : 'pending',
    },
    {
      label: verification
        ? verification.verification_status === 'successful_simulation'
          ? 'Verified'
          : 'Verification failed'
        : 'Verifying',
      state: verification
        ? verification.verification_status === 'successful_simulation'
          ? 'done'
          : 'failed'
        : execution && execution.execution_state !== 'failed_simulated'
          ? 'current'
          : 'pending',
    },
  ]
  if (item.rollback) steps.push({ label: 'Rolled back', state: 'rolled' })
  return steps
}

const METRIC_ROWS: [string, string, string][] = [
  ['Attack paths after', 'expected_attack_paths_after', 'actual_attack_paths_after'],
  ['Critical targets after', 'expected_critical_targets_after', 'actual_critical_targets_after'],
  ['Blast radius after', 'expected_blast_radius_after', 'actual_blast_radius_after'],
]

function show(value: unknown): string {
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  if (typeof value === 'number' || typeof value === 'string') return String(value)
  if (Array.isArray(value)) return value.length ? value.join(', ') : 'none'
  return 'n/a'
}

export function VerificationPage() {
  const selection = useBlueAgentSelection()
  const workflow = useOptionalAutonomyWorkflow()
  const [items, setItems] = useState<Orchestration[]>([])
  const [selected, setSelected] = useState<Orchestration | null>(null)
  const [role, setRole] = useState<'analyst' | 'administrator'>('analyst')
  const [reason, setReason] = useState('Approved for synthetic demonstration only.')
  const [error, setError] = useState<string | null>(null)
  const liveId = workflow?.orchestration?.orchestration_id ?? null

  useEffect(() => {
    void listOrchestrations()
      .then((rows) => {
        setItems(rows)
        const wanted = selection.orchestrationId || liveId
        const target = wanted ? rows.find((row) => row.orchestration_id === wanted) : undefined
        setSelected(target ?? rows[0] ?? null)
      })
      .catch(() => {
        setError('Synthetic orchestration data is unavailable.')
      })
    // Initial load only; later selections come from the selector or URL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!selection.orchestrationId) return
    void getOrchestration(selection.orchestrationId)
      .then(setSelected)
      .catch(() => undefined)
  }, [selection.orchestrationId])

  const update = (promise: Promise<Orchestration>) =>
    void promise
      .then((value) => {
        setError(null)
        setSelected(value)
        setItems((current) =>
          current.map((item) => (item.orchestration_id === value.orchestration_id ? value : item)),
        )
        void workflow?.refresh()
      })
      .catch(() => {
        setError('The requested synthetic transition is not valid.')
      })

  const approval = selected?.approvals.find((item) => item.approval_state === 'pending')
  const canApprove = Boolean(
    approval && (approval.required_role === role || role === 'administrator'),
  )
  const execution = selected?.executions[0] ?? null
  const verification = selected?.verifications[0] ?? null
  const metrics = verification?.metrics ?? {}
  const state = orchestrationState(selected?.current_state)

  return (
    <section className="page-stack" aria-labelledby="verification-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Defence · Verification</p>
          <h1 id="verification-title">Verification &amp; Recovery</h1>
          <p>
            Human approval, synthetic execution, dual-check verification (security effect AND
            operational health) and rollback. No real defensive action is performed.
          </p>
        </div>
        <div className="btn-row shrink-0">
          {workflow?.autonomy ? <AutonomyModePill mode={workflow.autonomy.mode} /> : null}
          <Link className="card-link" to="/workflow">
            Change autonomy mode
          </Link>
        </div>
      </header>

      {error ? (
        <p role="alert" className="error-state">
          {error}
        </p>
      ) : null}

      <Panel
        title="Orchestration"
        actions={
          selected ? (
            <Badge tone={state.tone} dot>
              {state.label}
            </Badge>
          ) : null
        }
      >
        <div className="grid gap-3">
          <label className="field max-w-md">
            <span>Selected orchestration</span>
            <select
              value={selected?.orchestration_id ?? ''}
              onChange={(event) => {
                selection.setOrchestrationId(event.target.value)
                setSelected(
                  items.find((item) => item.orchestration_id === event.target.value) ?? null,
                )
              }}
            >
              <option value="">No orchestration</option>
              {items.map((item) => (
                <option key={item.orchestration_id} value={item.orchestration_id}>
                  {item.orchestration_id.slice(0, 8)} · {humanize(item.current_state)}
                  {item.orchestration_id === liveId ? ' · live run' : ''}
                </option>
              ))}
            </select>
          </label>
          {selected ? (
            <>
              <div className="lifecycle" aria-label="Execution lifecycle">
                {lifecycleOf(selected).map((step, index, all) => (
                  <span key={step.label} className="contents">
                    <span
                      className={cn(
                        'lifecycle-step',
                        step.state === 'done' && 'is-done',
                        step.state === 'current' && 'is-current',
                        step.state === 'failed' && 'is-failed',
                        step.state === 'rolled' && 'is-rolled',
                      )}
                    >
                      {step.label}
                    </span>
                    {index < all.length - 1 ? <span className="lifecycle-sep">→</span> : null}
                  </span>
                ))}
              </div>
              <KeyValue
                left
                rows={[
                  ['State', humanize(selected.current_state)],
                  ['Approval tier', humanize(selected.required_approval_tier)],
                  [
                    'Playbook',
                    selected.plan_steps[0]
                      ? `${selected.plan_steps[0].playbook_id} on ${selected.plan_steps[0].target_id}`
                      : '—',
                  ],
                ]}
              />
            </>
          ) : (
            <p className="m-0 text-[0.8rem] text-[var(--text-faint)]">
              No synthetic response orchestration has been created.
            </p>
          )}
        </div>
      </Panel>

      {selected ? (
        <div className="split-2">
          <div className="grid content-start gap-3">
            <Panel
              title="Expected objective vs observed outcome"
              icon={<ShieldCheck className="size-4" />}
            >
              {verification ? (
                <div className="grid gap-3">
                  <Badge
                    tone={
                      verification.verification_status === 'successful_simulation' ? 'ok' : 'danger'
                    }
                  >
                    {humanize(verification.verification_status)}
                  </Badge>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Measure</th>
                        <th className="num">Expected</th>
                        <th className="num">Observed</th>
                      </tr>
                    </thead>
                    <tbody>
                      {METRIC_ROWS.map(([label, expected, actual]) => (
                        <tr key={label}>
                          <td className="is-primary">{label}</td>
                          <td className="num">{show(metrics[expected])}</td>
                          <td className="num">{show(metrics[actual])}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <KeyValue
                    rows={[
                      ['Security effect confirmed', show(metrics.security_effect_confirmed)],
                      ['Expected containment met', show(metrics.expected_containment_met)],
                      ['Operational health ok', show(metrics.operational_health_ok)],
                      ['Bystander isolated assets', show(metrics.bystander_isolated_asset_ids)],
                      ['Operational disruption', show(metrics.operational_disruption)],
                    ]}
                  />
                  {verification.unintended_effects.length ? (
                    <p className="m-0 text-[0.76rem] text-[var(--warn-text)]">
                      Unintended effects: {verification.unintended_effects.join('; ')}
                    </p>
                  ) : null}
                </div>
              ) : (
                <p className="m-0 text-[0.8rem] text-[var(--text-faint)]">
                  {execution
                    ? 'Executed - run verification to compare the observed twin state with the expected objective.'
                    : 'Verification runs after synthetic execution.'}
                </p>
              )}
            </Panel>
            <Panel title="Recovery">
              {selected.rollback ? (
                <KeyValue
                  rows={[
                    ['State', humanize(selected.rollback.state)],
                    ['Reason', selected.rollback.reason],
                    ['Requested by', selected.rollback.requested_by],
                    ['Restored to', selected.rollback.restored_state_reference ?? '—'],
                  ]}
                />
              ) : (
                <p className="m-0 text-[0.8rem] text-[var(--text-faint)]">
                  {verification?.verification_status === 'successful_simulation'
                    ? 'Not required: verification met the expected objective. An administrator may still roll back.'
                    : 'Rollback is evaluated automatically when verification fails.'}
                </p>
              )}
            </Panel>
          </div>
          <div className="grid content-start gap-3">
            <Panel title="Human approval gate">
              {approval ? (
                <div className="grid gap-2">
                  <p className="m-0 text-[0.8rem]">
                    Required role: <strong>{approval.required_role}</strong>. Synthetic
                    demonstration identity only.
                  </p>
                  <label className="field">
                    <span>Simulated actor role</span>
                    <select
                      aria-label="Simulated actor role"
                      value={role}
                      onChange={(event) => {
                        setRole(event.target.value as typeof role)
                      }}
                    >
                      <option value="analyst">Demo SOC Analyst</option>
                      <option value="administrator">Demo Security Administrator</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>Decision reason</span>
                    <textarea
                      value={reason}
                      onChange={(event) => {
                        setReason(event.target.value)
                      }}
                    />
                  </label>
                  <div className="btn-row">
                    {(['approve', 'reject'] as const).map((decision) => (
                      <Button
                        key={decision}
                        variant={decision === 'approve' ? 'success' : 'danger'}
                        disabled={!canApprove || reason.length < 3}
                        onClick={() => {
                          update(
                            decideApproval(
                              selected.orchestration_id,
                              approval.approval_request_id,
                              {
                                actor_role: role,
                                actor_display_name:
                                  role === 'administrator'
                                    ? 'Demo Security Administrator'
                                    : 'Demo SOC Analyst',
                                decision,
                                reason,
                              },
                            ),
                          )
                        }}
                      >
                        {decision === 'approve' ? <Check /> : <X />}
                        {decision === 'approve' ? 'Approve' : 'Reject'}
                      </Button>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="m-0 text-[0.8rem] text-[var(--text-faint)]">
                  No pending human approval.
                </p>
              )}
            </Panel>
            <Panel title="Synthetic execution, verification & rollback">
              <div className="grid gap-2">
                <div className="btn-row">
                  <Button
                    disabled={selected.current_state !== 'approved'}
                    onClick={() => {
                      update(executeSynthetic(selected.orchestration_id))
                    }}
                  >
                    <Play /> Execute in Synthetic Twin
                  </Button>
                  <Button
                    variant="outline"
                    disabled={selected.current_state !== 'synthetic_execution_completed'}
                    onClick={() => {
                      update(verifySynthetic(selected.orchestration_id))
                    }}
                  >
                    <ShieldCheck /> Verify Simulated Outcome
                  </Button>
                  <Button
                    variant="outline"
                    disabled={
                      !['verified', 'rollback_recommended'].includes(selected.current_state) ||
                      !execution?.reversible
                    }
                    onClick={() => {
                      update(
                        rollbackSynthetic(
                          selected.orchestration_id,
                          'Restore the synthetic demonstration baseline.',
                        ),
                      )
                    }}
                  >
                    <RotateCcw /> Roll Back Synthetic State
                  </Button>
                </div>
                {execution ? (
                  <p className="m-0 text-[0.78rem] text-[var(--text-dim)]">
                    Execution state: {humanize(execution.execution_state)}. Applied in synthetic
                    twin: {execution.changed_node_ids.length} nodes and{' '}
                    {execution.changed_edge_ids.length} relationships.
                  </p>
                ) : null}
              </div>
            </Panel>
            <Panel title="Agent decisions" scroll className="max-h-[22rem]">
              <ol className="m-0 grid list-none gap-1.5 p-0">
                {selected.decisions.map((decision) => (
                  <li key={decision.agent_decision_id} className="inset text-[0.76rem]">
                    <strong className="text-[var(--text)]">{decision.agent_name}</strong>{' '}
                    <Badge tone="neutral">
                      {humanize(decision.decision_type)}: {humanize(decision.decision)}
                    </Badge>
                    <p className="m-0 mt-1 text-[var(--text-dim)]">{decision.rationale}</p>
                  </li>
                ))}
              </ol>
            </Panel>
          </div>
        </div>
      ) : null}
    </section>
  )
}
