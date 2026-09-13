import { useEffect, useState } from 'react'

import { Button } from '../../components/ui/button'
import { Card, CardContent, CardHeader } from '../../components/ui/card'
import { Badge } from '../../components/ui/badge'
import { getAutonomyConfig, setAutonomyMode } from '../../services/autonomyApi'
import {
  decideApproval,
  executeSynthetic,
  getOrchestration,
  listOrchestrations,
  rollbackSynthetic,
  verifySynthetic,
} from '../../services/orchestrationApi'
import type { AutonomyConfig, AutonomyMode } from '../../types/autonomy'
import type { Orchestration } from '../../types/orchestration'
import { useBlueAgentSelection } from './useBlueAgentSelection'

function label(value: string) {
  return value.replaceAll('_', ' ')
}

function formatMetric(value: unknown): string {
  if (value === undefined) return 'n/a'
  if (typeof value === 'boolean' || typeof value === 'number' || typeof value === 'string')
    return String(value)
  return 'n/a'
}

const MODE_DESCRIPTIONS: Record<AutonomyMode, string> = {
  observe: 'Monitor only - detection/evidence only, no response plan is generated.',
  recommend: 'Generate and rank candidate plans but never execute automatically.',
  approval_required:
    'Generate and validate a plan; execution requires the appropriate synthetic analyst/administrator approval.',
  autonomous:
    'Eligible low-impact, reversible, policy-passing actions may execute automatically; everything else still requires approval.',
}

function AutonomyControl() {
  const [config, setConfig] = useState<AutonomyConfig | null>(null)
  const [pendingMode, setPendingMode] = useState<AutonomyMode | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = () =>
    void getAutonomyConfig()
      .then(setConfig)
      .catch(() => {
        setError('The synthetic autonomy configuration is unavailable.')
      })
  useEffect(refresh, [])

  async function apply(mode: AutonomyMode, confirm: boolean) {
    setBusy(true)
    setError(null)
    try {
      const updated = await setAutonomyMode(mode, 'Demo SOC Analyst', confirm)
      setConfig(updated)
      setPendingMode(null)
    } catch {
      setError('Raising autonomy to AUTONOMOUS requires explicit confirmation.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <h2 className="panel-title">Autonomy mode</h2>
      </CardHeader>
      <CardContent>
        {error ? (
          <p role="alert" className="text-red-700">
            {error}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Autonomy mode">
          {(['observe', 'recommend', 'approval_required', 'autonomous'] as const).map((mode) => (
            <Button
              key={mode}
              variant={config?.mode === mode ? undefined : 'outline'}
              disabled={busy}
              onClick={() => {
                if (mode === 'autonomous') setPendingMode(mode)
                else void apply(mode, false)
              }}
            >
              {label(mode)}
            </Button>
          ))}
        </div>
        {pendingMode === 'autonomous' ? (
          <div className="mt-3 rounded border border-amber-300 bg-amber-50 p-3 text-sm">
            <p>
              Raising autonomy to AUTONOMOUS lets eligible low-impact, reversible, policy-passing
              actions execute without a human approval step. Confirm to proceed.
            </p>
            <div className="mt-2 flex gap-2">
              <Button disabled={busy} onClick={() => void apply('autonomous', true)}>
                Confirm AUTONOMOUS
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setPendingMode(null)
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : null}
        {config ? (
          <p className="mt-3 text-sm text-slate-600">
            Current: <strong>{label(config.mode)}</strong> — {MODE_DESCRIPTIONS[config.mode]}
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}

export function VerificationPage() {
  const selection = useBlueAgentSelection()
  const [items, setItems] = useState<Orchestration[]>([])
  const [selected, setSelected] = useState<Orchestration | null>(null)
  const [role, setRole] = useState<'analyst' | 'administrator'>('analyst')
  const [reason, setReason] = useState('Approved for synthetic demonstration only.')
  const [error, setError] = useState<string | null>(null)

  const refresh = () =>
    void listOrchestrations()
      .then((rows) => {
        setItems(rows)
        const target = selection.orchestrationId
          ? rows.find((row) => row.orchestration_id === selection.orchestrationId)
          : undefined
        setSelected(target ?? rows[0] ?? null)
      })
      .catch(() => {
        setError('Synthetic orchestration data is unavailable.')
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(refresh, [])

  useEffect(() => {
    if (!selection.orchestrationId) return
    void getOrchestration(selection.orchestrationId)
      .then(setSelected)
      .catch(() => {
        /* keep prior selection on transient failure */
      })
  }, [selection.orchestrationId])

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
  const verification = selected?.verifications[0]

  return (
    <section className="space-y-6" aria-labelledby="verification-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Blue Agent · Verification</p>
          <h1 id="verification-title">Verification &amp; Rollback</h1>
          <p>
            Human approval, synthetic execution, dual-check verification (security effect AND
            operational health) and automatic rollback. No real defensive action is performed.
          </p>
        </div>
      </header>
      <AutonomyControl />
      {error ? (
        <p role="alert" className="text-red-700">
          {error}
        </p>
      ) : null}
      <Card>
        <CardHeader>
          <h2 className="panel-title">Orchestration</h2>
        </CardHeader>
        <CardContent>
          <label>
            Selected orchestration
            <select
              value={selected?.orchestration_id ?? ''}
              onChange={(event) => {
                selection.setOrchestrationId(event.target.value)
                setSelected(
                  items.find((item) => item.orchestration_id === event.target.value) ?? null,
                )
              }}
              className="mt-1 block bg-slate-50 p-2"
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
            <p className="mt-2">
              <strong>State:</strong> {label(selected.current_state)} ·{' '}
              <strong>Approval tier:</strong> {label(selected.required_approval_tier)}
            </p>
          ) : (
            <p className="mt-2">No synthetic response orchestration has been created.</p>
          )}
        </CardContent>
      </Card>
      {selected ? (
        <>
          <Card>
            <CardHeader>
              <h2 className="panel-title">Agent decisions</h2>
            </CardHeader>
            <CardContent>
              <ol className="agent-workflow">
                {selected.decisions.map((decision) => (
                  <li key={decision.agent_decision_id}>
                    <strong>{decision.agent_name}</strong>
                    <span>
                      {label(decision.decision_type)}: {label(decision.decision)}
                    </span>
                    <small>{decision.rationale}</small>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <h2 className="panel-title">Human approval gate</h2>
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
                      className="mt-1 block bg-slate-50 p-2"
                    >
                      <option value="analyst">Demo SOC Analyst</option>
                      <option value="administrator">Demo Security Administrator</option>
                    </select>
                  </label>
                  <label className="mt-2 block">
                    Decision reason
                    <textarea
                      value={reason}
                      onChange={(event) => {
                        setReason(event.target.value)
                      }}
                      className="mt-1 block w-full bg-slate-50 p-2"
                    />
                  </label>
                  <div className="mt-2 flex gap-2">
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
              <h2 className="panel-title">Synthetic execution, verification &amp; rollback</h2>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
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
                <p className="mt-3 text-sm">
                  Execution state: {label(selected.executions[0].execution_state)}. Applied in
                  synthetic twin: {selected.executions[0].changed_node_ids.length} nodes and{' '}
                  {selected.executions[0].changed_edge_ids.length} relationships.
                </p>
              ) : null}
              {verification ? (
                <div className="mt-3 text-sm">
                  <p>
                    Verification:{' '}
                    <Badge
                      className={
                        verification.verification_status === 'successful_simulation'
                          ? 'chip-healthy'
                          : 'chip-danger'
                      }
                    >
                      {label(verification.verification_status)}
                    </Badge>
                  </p>
                  <p className="mt-1">
                    Security effect confirmed:{' '}
                    {formatMetric(verification.metrics.security_effect_confirmed)} · Operational
                    health ok: {formatMetric(verification.metrics.operational_health_ok)}
                  </p>
                  <p className="mt-1">
                    Residual exposure score:{' '}
                    {formatMetric(verification.metrics.residual_exposure_score)}
                  </p>
                </div>
              ) : null}
              {selected.rollback ? (
                <div className="mt-3 rounded border border-slate-200 p-3 text-sm">
                  <p>
                    <strong>Rollback:</strong> {label(selected.rollback.state)}
                  </p>
                  <p className="mt-1">Reason: {selected.rollback.reason}</p>
                  <p className="mt-1">Requested by: {selected.rollback.requested_by}</p>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </>
      ) : null}
    </section>
  )
}
