import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { BlastRadiusPanel } from '../components/topology/BlastRadiusPanel'
import * as blastRadiusApi from '../services/blastRadiusApi'
import * as topologyApi from '../services/topologyApi'
import type { BlastRadiusResult } from '../types/blastRadius'
import type { InfrastructureNode, TopologySnapshot } from '../types/topology'

vi.mock('../services/blastRadiusApi')
vi.mock('../services/topologyApi')

const nodes: InfrastructureNode[] = [
  {
    asset_id: 'auth-pod-01',
    display_name: 'Auth Pod',
    asset_type: 'service',
    zone: 'workload_zone',
    sensitivity: 'restricted',
    criticality: 'high',
    description: 'Synthetic auth pod.',
    synthetic: true,
    metadata: {},
  },
  {
    asset_id: 'iam-service-01',
    display_name: 'IAM Service',
    asset_type: 'identity_service',
    zone: 'identity_zone',
    sensitivity: 'highly_restricted',
    criticality: 'critical',
    description: 'Synthetic identity service.',
    synthetic: true,
    metadata: {},
  },
]

const snapshot: TopologySnapshot = {
  topology_version: 'aegisarena-cloud-topology-v1',
  nodes,
  edges: [],
  generated_at: '2026-09-13T00:00:00Z',
  synthetic: true,
}

const hypotheticalResult: BlastRadiusResult = {
  compromised_asset_ids: ['auth-pod-01'],
  directly_affected_asset_ids: ['auth-pod-01'],
  reachable_asset_ids: ['iam-service-01'],
  dependent_asset_ids: [],
  critical_assets_at_risk: ['iam-service-01'],
  trust_zones_reached: ['workload_zone', 'identity_zone'],
  representative_paths: [['auth-pod-01', 'iam-service-01']],
  reachable_count: 1,
  dependent_count: 0,
  critical_count: 1,
  score: {
    total: 25,
    reachable_contribution: 2,
    critical_asset_contribution: 10,
    sensitive_asset_contribution: 5,
    zone_crossing_contribution: 10,
  },
  mode: 'hypothetical',
  through_sequence_number: null,
  statement: 'From 1 compromised synthetic asset(s), 1 additional asset(s) are reachable.',
  synthetic: true,
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(topologyApi.getTopology).mockResolvedValue(snapshot)
  vi.mocked(blastRadiusApi.estimateBlastRadius).mockResolvedValue(hypotheticalResult)
})

describe('Blast Radius panel', () => {
  it('renders the result, mode label, and the graph overlay legend', async () => {
    render(<BlastRadiusPanel nodes={nodes} runId="" sequence={0} />)
    await userEvent.click(screen.getByRole('button', { name: 'Estimate blast radius' }))
    await waitFor(() => {
      expect(blastRadiusApi.estimateBlastRadius).toHaveBeenCalled()
    })
    expect(await screen.findByText('Hypothetical what-if')).toBeInTheDocument()
    expect(screen.getByText(hypotheticalResult.statement)).toBeInTheDocument()
    expect(screen.getAllByText('iam-service-01').length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Blast radius legend')).toBeInTheDocument()
    expect(
      screen.getByLabelText('Interactive synthetic infrastructure topology'),
    ).toBeInTheDocument()
  })

  it('shows the resolved sequence for an evidence-bound estimate', async () => {
    vi.mocked(blastRadiusApi.estimateBlastRadius).mockResolvedValue({
      ...hypotheticalResult,
      mode: 'evidence_bound',
      through_sequence_number: 3,
    })
    render(<BlastRadiusPanel nodes={nodes} runId="run-1" sequence={3} />)
    await userEvent.click(screen.getByRole('button', { name: 'Estimate blast radius' }))
    expect(await screen.findByText('Evidence-bound')).toBeInTheDocument()
    expect(screen.getByText('through sequence 3')).toBeInTheDocument()
  })

  it('requires at least one compromised asset', async () => {
    render(<BlastRadiusPanel nodes={nodes} runId="" sequence={0} />)
    await userEvent.click(screen.getByLabelText('Auth Pod'))
    await userEvent.click(screen.getByRole('button', { name: 'Estimate blast radius' }))
    expect(await screen.findByText('Select at least one compromised asset.')).toBeInTheDocument()
    expect(blastRadiusApi.estimateBlastRadius).not.toHaveBeenCalled()
  })

  it('surfaces a backend error without crashing', async () => {
    vi.mocked(blastRadiusApi.estimateBlastRadius).mockRejectedValue(new Error('boom'))
    render(<BlastRadiusPanel nodes={nodes} runId="" sequence={0} />)
    await userEvent.click(screen.getByRole('button', { name: 'Estimate blast radius' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The AegisArena backend is unavailable.',
    )
  })
})
