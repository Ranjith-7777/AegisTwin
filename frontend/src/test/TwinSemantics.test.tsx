import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { CyberDigitalTwin } from '../components/topology/CyberDigitalTwin'
import { TwinStateBanner } from '../components/topology/TwinLegend'
import type { SyntheticExecution } from '../types/orchestration'
import type { TopologySnapshot } from '../types/topology'

const topology: TopologySnapshot = {
  topology_version: 'aegisarena-cloud-topology-v1',
  generated_at: '2026-07-22T00:00:00Z',
  synthetic: true,
  nodes: [
    {
      asset_id: 'external-user-01',
      display_name: 'External User',
      asset_type: 'external_client',
      zone: 'edge_zone',
      sensitivity: 'public',
      criticality: 'low',
      description: 'Synthetic external client.',
      synthetic: true,
      metadata: {},
    },
    {
      asset_id: 'api-gateway-01',
      display_name: 'API Gateway',
      asset_type: 'api_gateway',
      zone: 'edge_zone',
      sensitivity: 'internal',
      criticality: 'high',
      description: 'Synthetic gateway.',
      synthetic: true,
      metadata: {},
    },
  ],
  edges: [],
}

const proposal = { changed_node_ids: ['api-gateway-01'], changed_edge_ids: [] }

function execution(state: string): SyntheticExecution {
  return {
    execution_id: 'x-1',
    plan_step_id: 's-1',
    playbook_id: 'isolate-synthetic-endpoint',
    target_type: 'asset',
    target_id: 'api-gateway-01',
    execution_state: state,
    started_at: '2026-07-21T09:00:00Z',
    completed_at: '2026-07-21T09:00:00Z',
    mutation_summary: {},
    changed_node_ids: ['api-gateway-01'],
    changed_edge_ids: [],
    simulated_failure_reason: null,
    reversible: true,
    synthetic: true,
  }
}

function gatewayNode() {
  return screen.getByLabelText(/^API Gateway,/)
}

describe('Digital Twin mitigation semantics', () => {
  it('shows a what-if proposal as a proposed overlay, never as mitigated', () => {
    render(<CyberDigitalTwin topology={topology} runState={null} responseImpact={proposal} />)
    const node = gatewayNode()
    expect(node.className).toContain('overlay-proposed')
    expect(node.className).not.toContain('state-synthetic-execution-applied')
    expect(node).toHaveTextContent('proposed')
    expect(node).not.toHaveTextContent('mitigated')
  })

  it('shows mitigated only from a persisted synthetic execution record', () => {
    render(
      <CyberDigitalTwin
        topology={topology}
        runState={null}
        responseImpact={proposal}
        syntheticExecution={execution('completed_simulated')}
      />,
    )
    const node = gatewayNode()
    expect(node.className).toContain('state-synthetic-execution-applied')
    // Once executed, the proposal is no longer drawn on top.
    expect(node.className).not.toContain('overlay-proposed')
    expect(node).toHaveTextContent('mitigated')
  })

  it('shows a rolled-back execution as restored', () => {
    render(
      <CyberDigitalTwin
        topology={topology}
        runState={null}
        syntheticExecution={execution('rolled_back_simulated')}
      />,
    )
    expect(gatewayNode().className).toContain('state-synthetic-rollback-restored')
    expect(gatewayNode()).toHaveTextContent('restored')
  })

  it('never marks anything for a failed simulated execution', () => {
    render(
      <CyberDigitalTwin
        topology={topology}
        runState={null}
        syntheticExecution={{ ...execution('failed_simulated'), changed_node_ids: [] }}
      />,
    )
    expect(gatewayNode().className).not.toContain('synthetic-execution-applied')
  })

  it('states proposed and executed mitigations explicitly in the banner', () => {
    const { rerender } = render(
      <TwinStateBanner execution={null} proposedCount={1} attackActive={false} />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('what-if only, not executed')
    rerender(
      <TwinStateBanner
        execution={execution('completed_simulated')}
        proposedCount={1}
        attackActive={false}
      />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('Mitigation executed in the twin')
  })
})
