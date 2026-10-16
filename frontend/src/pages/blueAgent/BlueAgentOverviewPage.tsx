import { Bot, Cpu } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Badge, type BadgeTone } from '../../components/ui/badge'
import { KeyValue, Panel } from '../../components/ui/panel'
import { BlueDecisionPanel } from '../../components/workflow/BlueDecisionPanel'
import { useOptionalAutonomyWorkflow } from '../../hooks/useAutonomyWorkflow'
import { humanize } from '../../lib/orchestrationState'
import { getAgentRegistry } from '../../services/agentsApi'
import { getAutonomyConfig } from '../../services/autonomyApi'
import { getOrchestration } from '../../services/orchestrationApi'
import type { AgentRegistry } from '../../types/agents'
import type { AutonomyConfig } from '../../types/autonomy'
import type { Orchestration } from '../../types/orchestration'
import { useBlueAgentSelection } from './useBlueAgentSelection'

const AUTONOMY_TONE: Record<string, BadgeTone> = {
  observe: 'neutral',
  recommend: 'accent',
  approval_required: 'warn',
  autonomous: 'ok',
}

/**
 * Blue Agent overview: the autonomy mode, the current response decision and
 * its lifecycle, and the registry of deterministic agents that produce it -
 * only computed and persisted state, no simulated "AI thinking".
 */
export function BlueAgentOverviewPage() {
  const selection = useBlueAgentSelection()
  const workflow = useOptionalAutonomyWorkflow()
  const [autonomy, setAutonomy] = useState<AutonomyConfig | null>(null)
  const [orchestration, setOrchestration] = useState<Orchestration | null>(null)
  const [registry, setRegistry] = useState<AgentRegistry | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void getAutonomyConfig()
      .then(setAutonomy)
      .catch(() => {
        setError('The synthetic autonomy configuration is unavailable.')
      })
    void getAgentRegistry()
      .then(setRegistry)
      .catch(() => {
        setRegistry(null)
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

  // An explicit URL selection wins; otherwise follow the live run.
  const activeOrchestration = selection.orchestrationId
    ? orchestration
    : (workflow?.orchestration ?? null)
  const mode = workflow?.autonomy ?? autonomy
  const approval = activeOrchestration?.approvals.find((item) => item.approval_state === 'pending')
  const execution = activeOrchestration?.executions[0]
  const verification = activeOrchestration?.verifications[0]
  const blueAgents = registry?.agents.filter((agent) => agent.side === 'blue') ?? []

  return (
    <section className="page-stack" aria-labelledby="blue-agent-overview-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Defence · Blue Agent</p>
          <h1 id="blue-agent-overview-title">Blue Agent Overview</h1>
          <p>
            A real snapshot of the autonomy mode, the selected synthetic response and the
            deterministic agents behind it - no simulated "AI thinking", only computed and persisted
            state.
          </p>
        </div>
      </header>
      {error ? (
        <p role="alert" className="error-state">
          {error}
        </p>
      ) : null}
      <div className="split-main">
        <div className="grid content-start gap-3">
          <Panel
            title="Selected synthetic response"
            icon={<Bot className="size-4" />}
            actions={
              activeOrchestration ? (
                <Link className="card-link" to="/blue-agent/verification">
                  Verification
                </Link>
              ) : null
            }
          >
            {!activeOrchestration ? (
              <p className="m-0 text-[0.82rem] text-[var(--text-dim)]">
                No synthetic response orchestration selected. Run a scenario (the Blue workflow
                responds automatically) or use{' '}
                <Link to="/blue-agent/response-plans" className="card-link">
                  Response Plans
                </Link>{' '}
                to compare candidates and create one.
              </p>
            ) : (
              <KeyValue
                left
                rows={[
                  [
                    'Response action',
                    activeOrchestration.plan_steps[0]
                      ? `${humanize(activeOrchestration.plan_steps[0].playbook_id)} → ${humanize(activeOrchestration.plan_steps[0].target_type)} ${activeOrchestration.plan_steps[0].target_id}`
                      : 'No plan step recorded',
                  ],
                  ['Orchestration state', humanize(activeOrchestration.current_state)],
                  [
                    'Approval status',
                    approval
                      ? `pending (${approval.required_role})`
                      : activeOrchestration.approvals.length > 0
                        ? 'decided'
                        : 'not required',
                  ],
                  [
                    'Execution status',
                    execution ? humanize(execution.execution_state) : 'not yet executed',
                  ],
                  [
                    'Verification result',
                    verification ? humanize(verification.verification_status) : 'not yet verified',
                  ],
                ]}
              />
            )}
          </Panel>
          {workflow ? <BlueDecisionPanel className="max-h-[32rem]" /> : null}
        </div>
        <div className="grid content-start gap-3">
          <Panel
            title="Autonomy mode"
            actions={
              <Link to="/workflow" className="card-link">
                Change mode
              </Link>
            }
          >
            {mode ? (
              <div className="grid gap-1.5">
                <Badge tone={AUTONOMY_TONE[mode.mode] ?? 'neutral'} className="w-fit">
                  {humanize(mode.mode)}
                </Badge>
                <p className="m-0 text-[0.8rem] text-[var(--text-dim)]">{mode.description}</p>
                <p className="m-0 text-[0.72rem] text-[var(--text-faint)]">
                  Last changed by {mode.updated_by} at {new Date(mode.updated_at).toLocaleString()}
                </p>
              </div>
            ) : (
              <p className="m-0 text-[0.8rem] text-[var(--text-faint)]">
                Loading autonomy configuration…
              </p>
            )}
          </Panel>
          <Panel title="Agent roster" icon={<Cpu className="size-4" />}>
            {blueAgents.length > 0 ? (
              <ol className="m-0 grid list-none gap-2 p-0">
                {blueAgents.map((agent, index) => (
                  <li key={agent.agent_id} className="grid gap-0.5 text-[0.76rem]">
                    <span className="flex items-center gap-2">
                      <span className="stage-index">{String(index + 1).padStart(2, '0')}</span>
                      <strong className="text-[var(--text)]">{agent.display_name}</strong>
                    </span>
                    <span className="pl-6 text-[var(--text-faint)]">
                      {agent.implementation_type}
                    </span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="m-0 text-[0.78rem] text-[var(--text-faint)]">
                Agent registry unavailable.
              </p>
            )}
            <p className="m-0 mt-3 text-[0.72rem] text-[var(--text-faint)]">
              Deterministic, policy-governed agents. No language model or learned policy is
              involved; see the{' '}
              <Link className="card-link" to="/blue-agent/agent-workflow">
                decision trace
              </Link>
              .
            </p>
          </Panel>
        </div>
      </div>
    </section>
  )
}
