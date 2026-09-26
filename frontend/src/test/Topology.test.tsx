import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AssetInspector, PathInspection } from '../components/topology/TopologyPanels'
import {
  parseRunTopologyState,
  parseTopologyPathPage,
  parseTopologySnapshot,
} from '../services/topologyApi'
import type { InfrastructureNode, TopologyPath } from '../types/topology'

const node: InfrastructureNode = {
  asset_id: 'application-pod-01',
  display_name: 'Application Pod',
  asset_type: 'kubernetes_pod',
  zone: 'workload_zone',
  sensitivity: 'restricted',
  criticality: 'high',
  description: 'Synthetic application processing service.',
  synthetic: true,
  metadata: {},
}

describe('synthetic topology', () => {
  it('strictly validates snapshots and rejects malformed responses', () => {
    const snapshot = {
      topology_version: 'aegisarena-cloud-topology-v1',
      nodes: [node],
      edges: [],
      generated_at: '2026-07-22T00:00:00Z',
      synthetic: true,
    }
    expect(parseTopologySnapshot(snapshot)).toEqual(snapshot)
    expect(parseTopologySnapshot({ ...snapshot, synthetic: false })).toBeNull()
    expect(parseRunTopologyState({ synthetic: true })).toBeNull()
    expect(
      parseTopologyPathPage({ items: [{}], total: 1, maximum_paths: 3, synthetic: true }),
    ).toBeNull()
  })

  it('renders the asset inspector without confirmed-compromise wording', () => {
    render(<AssetInspector node={node} edges={[]} state={null} />)
    expect(screen.getByRole('heading', { name: 'Application Pod' })).toBeInTheDocument()
    expect(screen.getByText(/Synthetic asset/)).toBeInTheDocument()
    expect(screen.getByText(/No health, availability/)).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(/compromised/i)
  })

  it('labels predicted paths as hypothetical', () => {
    const path: TopologyPath = {
      path_type: 'predicted',
      ordered_node_ids: ['application-pod-01', 'simulation-egress-sink-01'],
      ordered_edge_ids: ['application-pod-01--simulation-egress-sink-01'],
      path_length: 1,
      evidence_source: 'persisted synthetic predicted evidence',
      through_sequence_number: 10,
      hypothetical: true,
      statement: 'Hypothetical path derived from synthetic ranked predictions.',
      synthetic: true,
    }
    render(<PathInspection path={path} />)
    expect(screen.getByText(path.statement)).toBeInTheDocument()
    expect(screen.getByText(/application-pod-01 → simulation-egress-sink-01/)).toBeInTheDocument()
  })
})
