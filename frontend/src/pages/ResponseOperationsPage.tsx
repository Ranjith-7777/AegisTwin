import { useEffect, useState } from 'react'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader } from '../components/ui/card'
import {
  decideApproval,
  executeSynthetic,
  listOrchestrations,
  rollbackSynthetic,
  verifySynthetic,
} from '../services/orchestrationApi'
import type { Orchestration } from '../types/orchestration'

const agents = [
  'Response Planner',
  'Impact Simulator',
  'Safety Governor',
  'Approval Router',
  'Synthetic Executor',
  'Verification',
  'Audit',
]
const label = (value: string) => value.replaceAll('_', ' ')

export function ResponseOperationsPage() {
  const [items, setItems] = useState<Orchestration[]>([])
  const [selected, setSelected] = useState<Orchestration | null>(null)
  const [role, setRole] = useState<'analyst' | 'administrator'>('analyst')
  const [reason, setReason] = useState('Approved for synthetic demonstration only.')
  const [error, setError] = useState<string | null>(null)
  const refresh = () =>
    void listOrchestrations()
      .then((rows) => {
        setItems(rows)
        setSelected(
          (current) =>
            rows.find((row) => row.orchestration_id === current?.orchestration_id) ??
            rows[0] ??
            null,
        )
      })
      .catch(() => {
        setError('Synthetic orchestration data is unavailable.')
      })
  useEffect(refresh, [])
  const approval = selected?.approvals.find((item) => item.approval_state === 'pending')
  const update = (promise: Promise<Orchestration>) =>
    void promise
      .then((value) => {
        setSelected(value)
        setItems((current) =>
          current.map((item) => (item.orchestration_id === value.orchestration_id ? value : item)),
        )
      })
      .catch(() => {
        setError('The requested synthetic transition is not valid.')
      })
  const canApprove = Boolean(
    approval && (approval.required_role === role || role === 'administrator'),
  )
  return (
    <section className="page-stack" aria-labelledby="operations-title">
      <header>
        <p className="eyebrow">Phase 7B · simulation agents</p>
        <h1 id="operations-title">Response Operations</h1>
        <p>
          Coordinate human-gated actions only inside the synthetic twin. No real defensive action is
          performed.
        </p>
      </header>
      {error ? (
        <p role="alert" tabIndex={-1}>
          {error}
        </p>
      ) : null}
      <Card>
        <CardHeader>
          <h2>Orchestration</h2>
        </CardHeader>
        <CardContent>
          <label>
            Selected orchestration
            <select
              value={selected?.orchestration_id ?? ''}
              onChange={(event) => {
                setSelected(
                  items.find((item) => item.orchestration_id === event.target.value) ?? null,
                )
              }}
            >
              <option value="">No orchestration</option>
              {items.map((item) => (
                <option key={item.orchestration_id} value={item.orchestration_id}>
                  {item.orchestration_id.slice(0, 8)} · {label(item.current_state)}
                </option>
              ))}
            </select>
          </label>
          {selected ? (
            <p>
              <strong>State:</strong> {label(selected.current_state)} ·{' '}
              <strong>Approval tier:</strong> {label(selected.required_approval_tier)}
            </p>
          ) : (
            <p>No synthetic response orchestration has been created.</p>
          )}
        </CardContent>
      </Card>
      {selected ? (
        <>
          <Card>
            <CardHeader>
              <h2>Simulation agent workflow</h2>
            </CardHeader>
            <CardContent>
              <ol className="agent-workflow">
                {agents.map((agent) => {
                  const decision = selected.decisions.find((item) =>
                    item.agent_name.startsWith(agent),
                  )
                  const active = selected.decisions.at(-1)?.next_agent?.startsWith(agent)
                  return (
                    <li key={agent}>
                      <strong>{agent}</strong>
                      <span>{decision ? 'completed' : active ? 'active' : 'waiting'}</span>
                      <small>{decision?.output_summary ?? 'Awaiting deterministic handoff.'}</small>
                    </li>
                  )
                })}
              </ol>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <h2>Ordered response plan</h2>
            </CardHeader>
            <CardContent>
              {selected.plan_steps.map((step) => (
                <article key={step.plan_step_id}>
                  <h3>
                    {step.step_number}. {label(step.playbook_id)}
                  </h3>
                  <p>
                    Target: {step.target_id} · {label(step.reversibility)} ·{' '}
                    {label(step.current_status)}
                  </p>
                  <p>{step.rationale}</p>
                </article>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <h2>Human approval gate</h2>
            </CardHeader>
            <CardContent>
              {approval ? (
                <>
                  <p>
                    Required role: <strong>{approval.required_role}</strong>. Synthetic
                    demonstration identity only.
                  </p>
                  <label>
                    Simulated actor role
                    <select
                      value={role}
                      onChange={(event) => {
                        setRole(event.target.value as typeof role)
                      }}
                    >
                      <option value="analyst">Demo SOC Analyst</option>
                      <option value="administrator">Demo Security Administrator</option>
                    </select>
                  </label>
                  <label>
                    Decision reason
                    <textarea
                      value={reason}
                      onChange={(event) => {
                        setReason(event.target.value)
                      }}
                    />
                  </label>
                  <div className="button-row">
                    <Button
                      disabled={!canApprove || reason.length < 3}
                      onClick={() => {
                        update(
                          decideApproval(selected.orchestration_id, approval.approval_request_id, {
                            actor_role: role,
                            actor_display_name:
                              role === 'administrator'
                                ? 'Demo Security Administrator'
                                : 'Demo SOC Analyst',
                            decision: 'approve',
                            reason,
                          }),
                        )
                      }}
                    >
                      Approve
                    </Button>
                    <Button
                      disabled={!canApprove || reason.length < 3}
                      variant="outline"
                      onClick={() => {
                        update(
                          decideApproval(selected.orchestration_id, approval.approval_request_id, {
                            actor_role: role,
                            actor_display_name:
                              role === 'administrator'
                                ? 'Demo Security Administrator'
                                : 'Demo SOC Analyst',
                            decision: 'reject',
                            reason,
                          }),
                        )
                      }}
                    >
                      Reject
                    </Button>
                  </div>
                </>
              ) : (
                <p>No pending human approval.</p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <h2>Synthetic execution and verification</h2>
            </CardHeader>
            <CardContent>
              <div className="button-row">
                <Button
                  disabled={selected.current_state !== 'approved'}
                  onClick={() => {
                    update(executeSynthetic(selected.orchestration_id))
                  }}
                >
                  Execute in Synthetic Twin
                </Button>
                <Button
                  disabled={selected.current_state !== 'synthetic_execution_completed'}
                  onClick={() => {
                    update(verifySynthetic(selected.orchestration_id))
                  }}
                >
                  Verify Simulated Outcome
                </Button>
                <Button
                  disabled={
                    !['verified', 'rollback_recommended'].includes(selected.current_state) ||
                    !selected.executions[0]?.reversible
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
                  Roll Back Synthetic State
                </Button>
              </div>
              {selected.executions[0] ? (
                <p>
                  Execution state: {label(selected.executions[0].execution_state)}. Applied in
                  synthetic twin: {selected.executions[0].changed_node_ids.length} nodes and{' '}
                  {selected.executions[0].changed_edge_ids.length} relationships.
                </p>
              ) : null}
              {selected.verifications[0] ? (
                <p>
                  Verification: {label(selected.verifications[0].verification_status)}. Residual
                  exposure score:{' '}
                  {String(selected.verifications[0].metrics.residual_exposure_score)}
                </p>
              ) : null}
            </CardContent>
          </Card>
        </>
      ) : null}
    </section>
  )
}
