import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { BlueAgentOverviewPage } from '../pages/blueAgent/BlueAgentOverviewPage'
import * as autonomyApi from '../services/autonomyApi'
import * as orchestrationApi from '../services/orchestrationApi'
import type { AutonomyConfig } from '../types/autonomy'
import type { Orchestration } from '../types/orchestration'

vi.mock('../services/autonomyApi')
vi.mock('../services/orchestrationApi')

const autonomy: AutonomyConfig = {
  mode: 'recommend',
  description: 'Generate and rank candidate plans but never execute automatically.',
  updated_by: 'system-default',
  updated_at: '2026-07-22T00:00:00Z',
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
  executions: [
    {
      execution_id: 'exec-1',
      plan_step_id: 'step-1',
      playbook_id: 'block-synthetic-route',
      target_type: 'relationship',
      target_id: 'a--b',
      execution_state: 'completed_simulated',
      started_at: '2026-07-22T00:00:00Z',
      completed_at: '2026-07-22T00:00:00Z',
      mutation_summary: {},
      changed_node_ids: [],
      changed_edge_ids: ['a--b'],
      simulated_failure_reason: null,
      reversible: true,
      synthetic: true,
    },
  ],
  verifications: [
    {
      verification_id: 'verify-1',
      execution_id: 'exec-1',
      verification_status: 'successful_simulation',
      metrics: { security_effect_confirmed: true, operational_health_ok: true },
      unintended_effects: [],
      started_at: '2026-07-22T00:00:00Z',
      completed_at: '2026-07-22T00:00:00Z',
      synthetic: true,
    },
  ],
  rollback: null,
}

beforeEach(() => {
  vi.mocked(autonomyApi.getAutonomyConfig).mockResolvedValue(autonomy)
  vi.mocked(orchestrationApi.getOrchestration).mockResolvedValue(orchestration)
})

describe('Blue Agent Overview tab', () => {
  it('shows an honest empty state with no orchestration selected', async () => {
    render(
      <MemoryRouter initialEntries={['/blue-agent/overview']}>
        <BlueAgentOverviewPage />
      </MemoryRouter>,
    )
    expect(await screen.findByText('recommend')).toBeInTheDocument()
    expect(screen.getByText(/No synthetic response orchestration selected/)).toBeInTheDocument()
  })

  it('shows real orchestration state when one is selected via the URL', async () => {
    render(
      <MemoryRouter initialEntries={['/blue-agent/overview?orchestration=orch-1']}>
        <BlueAgentOverviewPage />
      </MemoryRouter>,
    )
    expect(await screen.findByText('verified')).toBeInTheDocument()
    expect(screen.getByText('completed simulated')).toBeInTheDocument()
    expect(screen.getByText('successful simulation')).toBeInTheDocument()
  })
})
