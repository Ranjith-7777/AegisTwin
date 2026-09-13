import { useEffect, useState } from 'react'

import { Badge } from '../../components/ui/badge'
import { Card, CardContent, CardHeader } from '../../components/ui/card'
import { getAgentRegistry, getAgentTrace } from '../../services/agentsApi'
import { listOrchestrations } from '../../services/orchestrationApi'
import type { AgentDescriptor, AgentRegistry, AgentTrace } from '../../types/agents'
import type { Orchestration } from '../../types/orchestration'
import { useBlueAgentSelection } from './useBlueAgentSelection'

function label(value: string) {
  return value.replaceAll('_', ' ')
}

function AgentCard({
  agent,
  active,
  onSelect,
}: {
  agent: AgentDescriptor
  active: boolean
  onSelect: () => void
}) {
  return (
    <button
      onClick={onSelect}
      className={`w-full rounded border p-3 text-left transition ${
        agent.side === 'red' ? 'border-red-200 bg-red-50/40' : 'border-blue-200 bg-blue-50/40'
      } ${active ? 'ring-2 ring-slate-900' : ''}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold">{agent.display_name}</span>
        <Badge className={agent.side === 'red' ? 'chip-danger' : 'chip-accent'}>{agent.side}</Badge>
      </div>
      <p className="text-xs uppercase tracking-wide text-slate-500">Deterministic software agent</p>
      <p className="mt-1 text-sm text-slate-600">{agent.role}</p>
    </button>
  )
}

export function AgentWorkflowPage() {
  const selection = useBlueAgentSelection()
  const [registry, setRegistry] = useState<AgentRegistry | null>(null)
  const [orchestrations, setOrchestrations] = useState<Orchestration[]>([])
  const [trace, setTrace] = useState<AgentTrace | null>(null)
  const [selectedAgent, setSelectedAgent] = useState<AgentDescriptor | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void getAgentRegistry()
      .then(setRegistry)
      .catch(() => {
        setError('The synthetic agent registry is unavailable.')
      })
    void listOrchestrations()
      .then(setOrchestrations)
      .catch(() => {
        setOrchestrations([])
      })
  }, [])

  useEffect(() => {
    if (!selection.orchestrationId) return
    void getAgentTrace(selection.orchestrationId)
      .then(setTrace)
      .catch(() => {
        setTrace(null)
      })
  }, [selection.orchestrationId])

  const redAgents = registry?.agents.filter((item) => item.side === 'red') ?? []
  const blueAgents = registry?.agents.filter((item) => item.side === 'blue') ?? []

  return (
    <section className="space-y-6" aria-labelledby="agent-workflow-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Blue Agent · Agent Workflow</p>
          <h1 id="agent-workflow-title">Agent Architecture</h1>
          <p>
            AegisArena runs exactly {registry?.total_agents ?? 7} functional agents:{' '}
            {registry?.red_agent_count ?? 1} Red-side and {registry?.blue_agent_count ?? 6}{' '}
            Blue-side. Detection models, incident correlation, MITRE mapping, the Attack Graph and
            Blast Radius are analytical subsystems those agents consult - never agents themselves.
          </p>
        </div>
      </header>
      {error ? (
        <p role="alert" className="text-red-700">
          {error}
        </p>
      ) : null}
      {registry ? (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {redAgents.map((agent) => (
              <AgentCard
                key={agent.agent_id}
                agent={agent}
                active={selectedAgent?.agent_id === agent.agent_id}
                onSelect={() => {
                  setSelectedAgent(agent)
                }}
              />
            ))}
          </div>
          <Card>
            <CardHeader>
              <h2 className="panel-title">Analytical subsystems (not agents)</h2>
            </CardHeader>
            <CardContent className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {registry.analytical_subsystems.map((subsystem) => (
                <div key={subsystem.subsystem_id} className="rounded border border-dashed p-3">
                  <p className="font-semibold">{subsystem.display_name}</p>
                  <p className="text-xs text-slate-500">
                    Consumed by: {subsystem.consumed_by.map(label).join(', ')}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">{subsystem.description}</p>
                </div>
              ))}
            </CardContent>
          </Card>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {blueAgents.map((agent) => (
              <AgentCard
                key={agent.agent_id}
                agent={agent}
                active={selectedAgent?.agent_id === agent.agent_id}
                onSelect={() => {
                  setSelectedAgent(agent)
                }}
              />
            ))}
          </div>
        </div>
      ) : (
        <Card>
          <CardContent>
            <p>Loading the synthetic agent registry…</p>
          </CardContent>
        </Card>
      )}
      {selectedAgent ? (
        <Card>
          <CardHeader>
            <h2 className="panel-title">{selectedAgent.display_name}</h2>
          </CardHeader>
          <CardContent>
            <p>{selectedAgent.description}</p>
            <dl className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
              <dt>Implementation</dt>
              <dd>{selectedAgent.implementation_type}</dd>
              <dt>Version</dt>
              <dd>{selectedAgent.version}</dd>
              <dt>Decision type</dt>
              <dd>{label(selectedAgent.decision_type)}</dd>
              <dt>Input</dt>
              <dd>{selectedAgent.input_types.join(', ')}</dd>
              <dt>Output</dt>
              <dd>{selectedAgent.output_types.join(', ')}</dd>
              <dt>Next handoff</dt>
              <dd>
                {selectedAgent.next_agent ? label(selectedAgent.next_agent) : 'none (terminal)'}
              </dd>
            </dl>
          </CardContent>
        </Card>
      ) : null}
      <Card>
        <CardHeader>
          <h2 className="panel-title">Live agent trace</h2>
        </CardHeader>
        <CardContent>
          <label>
            Orchestration
            <select
              aria-label="Trace orchestration"
              value={selection.orchestrationId}
              onChange={(event) => {
                selection.setOrchestrationId(event.target.value)
              }}
              className="mt-1 block bg-slate-50 p-2"
            >
              <option value="">No agent execution selected</option>
              {orchestrations.map((item) => (
                <option key={item.orchestration_id} value={item.orchestration_id}>
                  {item.orchestration_id.slice(0, 8)} · {label(item.current_state)}
                </option>
              ))}
            </select>
          </label>
          {!selection.orchestrationId ? (
            <p className="mt-3">No agent execution selected.</p>
          ) : trace ? (
            <ol className="agent-workflow mt-3">
              {trace.entries.map((entry) => (
                <li key={`${entry.agent_id}-${entry.sequence.toString()}`}>
                  <strong>
                    {entry.sequence}. {entry.agent_name}
                  </strong>
                  <span>
                    {label(entry.decision_type)}: {label(entry.decision)}
                    {entry.score !== null ? ` (score ${entry.score.toFixed(2)})` : ''}
                  </span>
                  <small>{entry.rationale}</small>
                  {entry.warnings.length > 0 ? (
                    <small className="text-amber-700">Warnings: {entry.warnings.join('; ')}</small>
                  ) : null}
                </li>
              ))}
              {trace.stopped_reason ? (
                <li>
                  <strong>Pipeline status</strong>
                  <small>{trace.stopped_reason}</small>
                </li>
              ) : null}
            </ol>
          ) : (
            <p className="mt-3">Loading trace…</p>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
