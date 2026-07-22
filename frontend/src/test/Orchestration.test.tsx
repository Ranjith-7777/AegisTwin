import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ResponseOperationsPage } from '../pages/ResponseOperationsPage'
import { AuditTrailPage } from '../pages/AuditTrailPage'
import * as orchestrationApi from '../services/orchestrationApi'
import type { Orchestration } from '../types/orchestration'

vi.mock('../services/orchestrationApi')

const orchestration: Orchestration = {
  orchestration_id: 'orch-1',
  simulation_run_id: 'run-1',
  model_id: 'model-1',
  incident_candidate_id: 'candidate-1',
  through_sequence_number: 10,
  orchestration_version: 'v1',
  current_state: 'awaiting_administrator_approval',
  selected_recommendation_id: 'rec-1',
  required_approval_tier: 'administrator_approval',
  created_by: 'Demo Operator (synthetic)',
  created_at: '2026-07-22T00:00:00Z',
  updated_at: '2026-07-22T00:00:00Z',
  synthetic: true,
  plan_steps: [
    {
      plan_step_id: 'step-1',
      step_number: 1,
      playbook_id: 'quarantine-synthetic-application',
      recommendation_id: 'rec-1',
      target_type: 'application_server',
      target_id: 'application-server-01',
      required_approval_tier: 'administrator_approval',
      reversibility: 'reversible',
      rationale: 'Synthetic evidence rationale.',
      expected_mutation: { operation: 'remove_incident_edges' },
      current_status: 'planned',
      synthetic: true,
    },
  ],
  decisions: [
    {
      agent_decision_id: 'decision-1',
      agent_name: 'Response Planner Simulation Agent',
      agent_version: 'v1',
      decision_type: 'plan_selection',
      input_reference_ids: ['rec-1'],
      output_summary: 'Selected primary synthetic action.',
      decision: 'selected',
      ranking_score: 0.8,
      rationale: 'Deterministic selection.',
      warnings: [],
      next_agent: 'Impact Simulation Agent',
      created_at: '2026-07-22T00:00:00Z',
      synthetic: true,
    },
  ],
  approvals: [
    {
      approval_request_id: 'approval-1',
      plan_step_id: 'step-1',
      required_role: 'administrator',
      approval_state: 'pending',
      requested_at: '2026-07-22T00:00:00Z',
      decided_at: null,
      decided_by: null,
      decision_reason: null,
      synthetic: true,
    },
  ],
  executions: [],
  verifications: [],
  rollback: null,
}

describe('Phase 7B synthetic orchestration', () => {
  beforeEach(() => {
    vi.mocked(orchestrationApi.listOrchestrations).mockResolvedValue([orchestration])
    vi.mocked(orchestrationApi.decideApproval).mockResolvedValue({
      ...orchestration,
      current_state: 'approved',
      approvals: orchestration.approvals.map((item) => ({
        ...item,
        approval_state: 'approved',
      })),
    })
    vi.mocked(orchestrationApi.getAudit).mockResolvedValue([
      {
        audit_event_id: 'audit-1',
        sequence_number: 1,
        event_type: 'orchestration_created',
        actor_type: 'human',
        actor_id: 'demo',
        actor_display_name: 'Demo Operator (synthetic)',
        previous_event_hash: '0'.repeat(64),
        event_hash: 'a'.repeat(64),
        canonical_payload: { to_state: 'planning' },
        created_at: '2026-07-22T00:00:00Z',
        synthetic: true,
      },
    ])
    vi.mocked(orchestrationApi.verifyAudit).mockResolvedValue({
      valid: true,
      event_count: 1,
      first_invalid_sequence: null,
      algorithm: 'SHA-256 canonical-json-chain-v1',
      synthetic: true,
    })
  })

  it('renders agent workflow and enforces administrator demonstration approval', async () => {
    const user = userEvent.setup()
    render(<ResponseOperationsPage />)
    expect(await screen.findByText('Simulation agent workflow')).toBeInTheDocument()
    expect(screen.getByText('Selected primary synthetic action.')).toBeInTheDocument()
    const approve = screen.getByRole('button', { name: 'Approve' })
    expect(approve).toBeDisabled()
    await user.selectOptions(screen.getByLabelText('Simulated actor role'), 'administrator')
    expect(approve).toBeEnabled()
    await user.click(approve)
    await waitFor(() => {
      expect(orchestrationApi.decideApproval).toHaveBeenCalledWith(
        'orch-1',
        'approval-1',
        expect.objectContaining({ actor_role: 'administrator', decision: 'approve' }),
      )
    })
    expect(screen.getByRole('button', { name: 'Execute in Synthetic Twin' })).toBeEnabled()
    expect(screen.getByText(/No real defensive action is performed/)).toBeInTheDocument()
  })

  it('renders and verifies the tamper-evident audit chain', async () => {
    const user = userEvent.setup()
    render(<AuditTrailPage />)
    expect(await screen.findByText(/#1 orchestration created/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Verify Audit Chain' }))
    expect(await screen.findByText('valid')).toBeInTheDocument()
    expect(screen.getByText(/does not prevent database administrators/)).toBeInTheDocument()
  })
})
