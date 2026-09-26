import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AgentWorkflowPage } from '../pages/blueAgent/AgentWorkflowPage'
import * as agentsApi from '../services/agentsApi'
import * as orchestrationApi from '../services/orchestrationApi'
import type { AgentRegistry, AgentTrace } from '../types/agents'
import type { Orchestration } from '../types/orchestration'

vi.mock('../services/agentsApi')
vi.mock('../services/orchestrationApi')

const registry: AgentRegistry = {
  agents: [
    {
      agent_id: 'synthetic_red_agent',
      display_name: 'Synthetic Red Agent / Scenario Engine',
      side: 'red',
      role: 'Generates deterministic synthetic adversary activity.',
      description: 'Not an LLM.',
      implementation_type: 'Deterministic scenario/event generator',
      version: 'aegisarena-scenario-engine-v1',
      input_types: ['RedScenarioDefinition'],
      decision_type: 'scenario_step_emission',
      output_types: ['TelemetryEvent (synthetic)'],
      next_agent: null,
      synthetic: true,
    },
    {
      agent_id: 'response_planner',
      display_name: 'Response Planner Agent',
      side: 'blue',
      role: 'Generates and ranks candidate defensive plans.',
      description: 'Reuses response_service.analyze().',
      implementation_type: 'Deterministic multi-candidate ranking agent',
      version: 'deterministic-resilience-agent-v2',
      input_types: ['IncidentCandidate'],
      decision_type: 'plan_selection',
      output_types: ['ranked candidate plans'],
      next_agent: 'impact_simulation',
      synthetic: true,
    },
  ],
  analytical_subsystems: [
    {
      subsystem_id: 'attack_graph',
      display_name: 'Attack Graph',
      description: 'Deterministic ranked attack-path analysis.',
      consumed_by: ['response_planner'],
      synthetic: true,
    },
  ],
  total_agents: 7,
  red_agent_count: 1,
  blue_agent_count: 6,
  synthetic: true,
}

const trace: AgentTrace = {
  orchestration_id: 'orch-1',
  entries: [
    {
      agent_id: 'response_planner',
      agent_name: 'Response Planner Simulation Agent',
      sequence: 1,
      timestamp: '2026-07-22T00:00:00Z',
      input_summary: 'rec-1',
      decision_type: 'plan_selection',
      decision: 'selected',
      rationale: 'Deterministic selection.',
      warnings: [],
      resource_ids: ['rec-1'],
      score: 0.8,
      next_agent: 'impact_simulation',
      status: 'reached',
      synthetic: true,
    },
  ],
  stopped_reason: null,
  synthetic: true,
}

const orchestration: Orchestration = {
  orchestration_id: 'orch-1',
  simulation_run_id: 'run-1',
  model_id: 'model-1',
  incident_candidate_id: 'candidate-1',
  through_sequence_number: 10,
  orchestration_version: 'v1',
  current_state: 'verified',
  selected_recommendation_id: 'rec-1',
  required_approval_tier: 'analyst_approval',
  created_by: 'Demo Operator (synthetic)',
  created_at: '2026-07-22T00:00:00Z',
  updated_at: '2026-07-22T00:00:00Z',
  synthetic: true,
  plan_steps: [],
  decisions: [],
  approvals: [],
  executions: [],
  verifications: [],
  rollback: null,
}

beforeEach(() => {
  vi.mocked(agentsApi.getAgentRegistry).mockResolvedValue(registry)
  vi.mocked(agentsApi.getAgentTrace).mockResolvedValue(trace)
  vi.mocked(orchestrationApi.listOrchestrations).mockResolvedValue([orchestration])
})

describe('Agent Workflow (professor-facing architecture view)', () => {
  it('renders exactly the real agents and subsystems, and shows an honest empty trace state', async () => {
    render(
      <MemoryRouter>
        <AgentWorkflowPage />
      </MemoryRouter>,
    )
    expect(await screen.findByText('Synthetic Red Agent / Scenario Engine')).toBeInTheDocument()
    expect(screen.getByText('Response Planner Agent')).toBeInTheDocument()
    expect(screen.getByText('Analytical subsystems (not agents)')).toBeInTheDocument()
    expect(screen.getByText('Attack Graph')).toBeInTheDocument()
    expect(screen.getByText('No agent execution selected.')).toBeInTheDocument()
  })

  it('opens agent detail on click and loads a real trace once an orchestration is selected', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <AgentWorkflowPage />
      </MemoryRouter>,
    )
    await user.click(await screen.findByText('Response Planner Agent'))
    expect(screen.getByText('plan_selection'.replaceAll('_', ' '))).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Trace orchestration'), 'orch-1')
    await waitFor(() => {
      expect(agentsApi.getAgentTrace).toHaveBeenCalledWith('orch-1')
    })
    expect(await screen.findByText('Deterministic selection.')).toBeInTheDocument()
  })
})
