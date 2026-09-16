import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Badge } from '../../components/ui/badge'
import { Card, CardContent, CardHeader } from '../../components/ui/card'
import { getAutonomyConfig } from '../../services/autonomyApi'
import { getOrchestration } from '../../services/orchestrationApi'
import type { AutonomyConfig } from '../../types/autonomy'
import type { Orchestration } from '../../types/orchestration'
import { useBlueAgentSelection } from './useBlueAgentSelection'

function label(value: string) {
  return value.replaceAll('_', ' ')
}

const AUTONOMY_TONE: Record<string, string> = {
  observe: 'chip-muted',
  recommend: 'chip-accent',
  approval_required: 'chip-warn',
  autonomous: 'chip-danger',
}

export function BlueAgentOverviewPage() {
  const selection = useBlueAgentSelection()
  const [autonomy, setAutonomy] = useState<AutonomyConfig | null>(null)
  const [orchestration, setOrchestration] = useState<Orchestration | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void getAutonomyConfig()
      .then(setAutonomy)
      .catch(() => {
        setError('The synthetic autonomy configuration is unavailable.')
      })
  }, [])

  useEffect(() => {
    if (!selection.orchestrationId) return
    void getOrchestration(selection.orchestrationId)
      .then(setOrchestration)
      .catch(() => {
        setOrchestration(null)
      })
  }, [selection.orchestrationId])
  const activeOrchestration = selection.orchestrationId ? orchestration : null

  const approval = activeOrchestration?.approvals.find((item) => item.approval_state === 'pending')
  const execution = activeOrchestration?.executions[0]
  const verification = activeOrchestration?.verifications[0]

  return (
    <section className="space-y-6" aria-labelledby="blue-agent-overview-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Blue Agent · Overview</p>
          <h1 id="blue-agent-overview-title">Blue Agent Overview</h1>
          <p>
            A real snapshot of the current autonomy mode and the selected synthetic response, if any
            - no simulated "AI thinking" animation, only computed and persisted state.
          </p>
        </div>
      </header>
      {error ? (
        <p role="alert" className="text-red-700">
          {error}
        </p>
      ) : null}
      <Card>
        <CardHeader>
          <h2 className="panel-title">Autonomy mode</h2>
          <Link to="/blue-agent/verification" className="card-link">
            Change mode
          </Link>
        </CardHeader>
        <CardContent>
          {autonomy ? (
            <>
              <Badge className={AUTONOMY_TONE[autonomy.mode] ?? 'chip-muted'}>
                {label(autonomy.mode)}
              </Badge>
              <p className="mt-2 text-sm">{autonomy.description}</p>
              <p className="mt-1 text-xs text-slate-500">
                Last changed by {autonomy.updated_by} at{' '}
                {new Date(autonomy.updated_at).toLocaleString()}
              </p>
            </>
          ) : (
            <p>Loading autonomy configuration…</p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <h2 className="panel-title">Selected synthetic response</h2>
        </CardHeader>
        <CardContent>
          {!activeOrchestration ? (
            <p>
              No synthetic response orchestration selected. Use{' '}
              <Link to="/blue-agent/response-plans" className="card-link">
                Response Plans
              </Link>{' '}
              to compare candidates and create one.
            </p>
          ) : (
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <dt>Response action</dt>
              <dd>
                {activeOrchestration.plan_steps[0]
                  ? `${label(activeOrchestration.plan_steps[0].playbook_id)} → ${activeOrchestration.plan_steps[0].target_type.replaceAll('_', ' ')} ${activeOrchestration.plan_steps[0].target_id}`
                  : 'No plan step recorded'}
              </dd>
              <dt>Orchestration state</dt>
              <dd>{label(activeOrchestration.current_state)}</dd>
              <dt>Approval status</dt>
              <dd>
                {approval
                  ? `pending (${approval.required_role})`
                  : activeOrchestration.approvals.length > 0
                    ? 'decided'
                    : 'not required'}
              </dd>
              <dt>Execution status</dt>
              <dd>{execution ? label(execution.execution_state) : 'not yet executed'}</dd>
              <dt>Verification result</dt>
              <dd>{verification ? label(verification.verification_status) : 'not yet verified'}</dd>
            </dl>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
