import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { WhatIfDigitalTwin } from '../pages/blueAgent/WhatIfDigitalTwin'
import * as topologyApi from '../services/topologyApi'
import type { CandidatePlanAssessment } from '../types/bluePlanning'
import type { InfrastructureNode, TopologySnapshot } from '../types/topology'

vi.mock('../services/topologyApi')

const nodes: InfrastructureNode[] = [
  {
    asset_id: 'external-user-01',
    display_name: 'External User',
    asset_type: 'external_client',
    zone: 'edge_zone',
    sensitivity: 'standard',
    criticality: 'low',
    description: 'Synthetic external user.',
    synthetic: true,
    metadata: {},
  },
  {
    asset_id: 'api-gateway-01',
    display_name: 'API Gateway',
    asset_type: 'api_gateway',
    zone: 'edge_zone',
    sensitivity: 'standard',
    criticality: 'medium',
    description: 'Synthetic API gateway.',
    synthetic: true,
    metadata: {},
  },
]

const snapshot: TopologySnapshot = {
  topology_version: 'aegisarena-cloud-topology-v1',
  nodes,
  edges: [
    {
      edge_id: 'external-user-01--api-gateway-01',
      source_asset_id: 'external-user-01',
      destination_asset_id: 'api-gateway-01',
      relationship_type: 'expected_relationship',
      protocol_label: 'https',
      direction: 'directed',
      permitted: true,
      trust_level: 'standard',
      synthetic: true,
      metadata: {},
    },
  ],
  generated_at: '2026-09-13T00:00:00Z',
  synthetic: true,
}

const candidate: CandidatePlanAssessment = {
  recommendation_id: 'rec-1',
  playbook_id: 'quarantine-synthetic-ingress-edge',
  playbook_name: "Quarantine the attacker's ingress route",
  action_type: 'edge_restriction',
  target_type: 'relationship',
  target_id: 'external-user-01--api-gateway-01',
  required_approval_tier: 'automatic_candidate',
  reversibility: 'reversible',
  operational_impact: 'low',
  security_gain_evidence: {
    attack_paths_before: 1,
    attack_paths_after: 0,
    top_attack_path_score_before: 65,
    top_attack_path_score_after: 0,
    critical_targets_reachable_before: 1,
    critical_targets_reachable_after: 0,
    blast_radius_reachable_before: 8,
    blast_radius_reachable_after: 8,
    blast_radius_critical_before: 11,
    blast_radius_critical_after: 11,
    security_gain: 34.5,
  },
  utility_score: {
    security_gain: 34.5,
    critical_asset_protection: 20,
    blast_radius_reduction: 0,
    evidence_quality: 14.4,
    reversibility_bonus: 10,
    operational_impact_penalty: 0,
    total: 78.9,
  },
  policy_pass: true,
  policy_failed_ids: [],
  recommended: true,
  changed_node_ids: [],
  changed_edge_ids: ['external-user-01--api-gateway-01'],
  synthetic: true,
}

beforeEach(() => {
  vi.mocked(topologyApi.getTopology).mockResolvedValue(snapshot)
})

describe('What-If Digital Twin', () => {
  it('renders the graph with a hypothetical-not-executed label and real mutation ids', async () => {
    render(<WhatIfDigitalTwin candidate={candidate} />)
    expect(
      await screen.findByLabelText('Interactive synthetic infrastructure topology'),
    ).toBeInTheDocument()
    expect(screen.getByText('Hypothetical - not executed')).toBeInTheDocument()
    // Simulated-after is the default view; its summary must cite the real
    // mutation counts from the API-provided candidate, never invented ones.
    expect(screen.getByText(/1 relationship\(s\) and 0 asset\(s\)/)).toBeInTheDocument()
    expect(screen.getByText(/Remaining attack-path risk: 0 path\(s\)/)).toBeInTheDocument()
  })

  it('toggles between before and simulated-after modes', async () => {
    const user = userEvent.setup()
    render(<WhatIfDigitalTwin candidate={candidate} />)
    await screen.findByLabelText('Interactive synthetic infrastructure topology')

    await user.click(screen.getByRole('button', { name: 'Before response' }))
    expect(
      screen.getByText(/Before response: the real current synthetic topology/),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Simulated after response' }))
    expect(screen.getByText(/Simulated after: 1 relationship\(s\)/)).toBeInTheDocument()
  })

  it('surfaces a topology load failure without crashing', async () => {
    vi.mocked(topologyApi.getTopology).mockRejectedValue(new Error('boom'))
    render(<WhatIfDigitalTwin candidate={candidate} />)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The synthetic topology is unavailable for the what-if view.',
    )
  })
})
