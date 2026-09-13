import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AttackPathsPanel } from '../components/topology/AttackPathsPanel'
import * as attackGraphApi from '../services/attackGraphApi'
import * as topologyApi from '../services/topologyApi'
import type { AttackPathAnalysisResult } from '../types/attackGraph'
import type { InfrastructureNode, TopologySnapshot } from '../types/topology'

vi.mock('../services/attackGraphApi')
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
    asset_id: 'cloud-database-01',
    display_name: 'Cloud Database',
    asset_type: 'database',
    zone: 'data_zone',
    sensitivity: 'highly_restricted',
    criticality: 'critical',
    description: 'Synthetic database.',
    synthetic: true,
    metadata: {},
  },
]

const snapshot: TopologySnapshot = {
  topology_version: 'aegisarena-cloud-topology-v1',
  nodes,
  edges: [
    {
      edge_id: 'external-user-01--cloud-database-01',
      source_asset_id: 'external-user-01',
      destination_asset_id: 'cloud-database-01',
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

const analysis: AttackPathAnalysisResult = {
  source_asset_id: 'external-user-01',
  target_asset_id: null,
  path_type: 'potential',
  simulation_run_id: null,
  model_id: null,
  through_sequence_number: null,
  max_depth: 6,
  max_paths: 5,
  total_candidates_considered: 3,
  synthetic: true,
  paths: [
    {
      path_id: 'external-user-01-cloud-database-01:potential',
      path_type: 'potential',
      source_asset_id: 'external-user-01',
      target_asset_id: 'cloud-database-01',
      ordered_asset_ids: ['external-user-01', 'cloud-database-01'],
      hop_count: 1,
      trust_boundaries_crossed: ['edge_zone->data_zone'],
      privilege_escalation: false,
      target_criticality: 'critical',
      target_sensitivity: 'highly_restricted',
      evidence_asset_ids: [],
      through_sequence_number: null,
      synthetic: true,
      statement: 'potential path: external-user-01 -> cloud-database-01 (1 hop).',
      score: {
        total: 80,
        exposure_contribution: 25,
        privilege_contribution: 0,
        critical_target_contribution: 30,
        boundary_crossing_contribution: 25,
        evidence_contribution: 0,
        length_penalty: 0,
      },
      steps: [
        {
          sequence: 1,
          source_asset_id: 'external-user-01',
          destination_asset_id: 'cloud-database-01',
          edge_id: 'external-user-01--cloud-database-01',
          relationship_type: 'expected_relationship',
          attack_semantics: 'reads_from',
          reason: 'the source has a declared read relationship to this asset',
          trust_boundary_crossed: true,
          source_zone: 'edge_zone',
          destination_zone: 'data_zone',
          privileged: false,
          synthetic: true,
        },
      ],
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(topologyApi.getTopology).mockResolvedValue(snapshot)
  vi.mocked(attackGraphApi.analyzeAttackPaths).mockResolvedValue(analysis)
})

describe('Attack Paths panel', () => {
  it('queries, lists ranked paths, and focuses one selected path with its detail', async () => {
    render(<AttackPathsPanel nodes={nodes} runId="" modelId="" sequence={0} />)
    await userEvent.click(screen.getByRole('button', { name: 'Find attack paths' }))
    await waitFor(() => {
      expect(attackGraphApi.analyzeAttackPaths).toHaveBeenCalled()
    })

    // the ranked path is selectable, not shown as one giant simultaneous list
    const pathButton = await screen.findByRole('button', { name: /cloud-database-01.*1 hop/ })
    expect(pathButton).toBeInTheDocument()

    // selecting it reveals the textual explanation and score decomposition
    await userEvent.click(pathButton)
    expect(
      await screen.findByText('potential path: external-user-01 -> cloud-database-01 (1 hop).'),
    ).toBeInTheDocument()
    expect(screen.getByText(/Priority score: 80.0 \/ 100/)).toBeInTheDocument()
    expect(screen.getByText(/crosses trust boundary/)).toBeInTheDocument()

    // the graph canvas is rendered for the focused path
    expect(
      screen.getByLabelText('Interactive synthetic infrastructure topology'),
    ).toBeInTheDocument()
  })

  it('labels the active path type distinctly', async () => {
    render(<AttackPathsPanel nodes={nodes} runId="" modelId="" sequence={0} />)
    expect(
      screen.getByText(/Could this happen given the declared architecture/),
    ).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByDisplayValue('potential'), 'observed')
    expect(
      screen.getByText(/Has this actually happened, per real generated telemetry/),
    ).toBeInTheDocument()
  })

  it('shows an empty state when no path is found', async () => {
    vi.mocked(attackGraphApi.analyzeAttackPaths).mockResolvedValue({
      ...analysis,
      paths: [],
      total_candidates_considered: 0,
    })
    render(<AttackPathsPanel nodes={nodes} runId="" modelId="" sequence={0} />)
    await userEvent.click(screen.getByRole('button', { name: 'Find attack paths' }))
    expect(await screen.findByText('No attack path found for this query.')).toBeInTheDocument()
  })

  it('surfaces a backend error without crashing', async () => {
    vi.mocked(attackGraphApi.analyzeAttackPaths).mockRejectedValue(new Error('boom'))
    render(<AttackPathsPanel nodes={nodes} runId="" modelId="" sequence={0} />)
    await userEvent.click(screen.getByRole('button', { name: 'Find attack paths' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The AegisArena backend is unavailable.',
    )
  })
})
