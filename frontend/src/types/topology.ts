export type TopologyPathType = 'expected' | 'observed' | 'correlated' | 'predicted'

export interface InfrastructureNode {
  asset_id: string
  display_name: string
  asset_type: string
  zone: string
  sensitivity: string
  criticality: string
  description: string
  synthetic: true
  metadata: Record<string, unknown>
}

export interface InfrastructureEdge {
  edge_id: string
  source_asset_id: string
  destination_asset_id: string
  relationship_type: string
  protocol_label: string | null
  direction: 'directed'
  permitted: boolean
  trust_level: string
  synthetic: true
  metadata: Record<string, unknown>
}

export interface TopologySnapshot {
  topology_version: string
  nodes: InfrastructureNode[]
  edges: InfrastructureEdge[]
  generated_at: string
  synthetic: true
}

export interface RunTopologyState {
  state_version: 'live-topology-state-v1'
  simulation_run_id: string
  model_id: string | null
  observed_asset_ids: string[]
  observed_edge_ids: string[]
  correlated_asset_ids: string[]
  correlated_edge_ids: string[]
  predicted_asset_ids: string[]
  predicted_edge_ids: string[]
  anomalous_observed_asset_ids: string[]
  anomalous_observed_edge_ids: string[]
  unexpected_observed_edge_ids: string[]
  event_mappings: TopologyEventMapping[]
  predicted_paths: TopologyPath[]
  current_sequence_limit: number
  synthetic: true
}

export interface TopologyEventMapping {
  event_id: string
  sequence_number: number
  source_asset_id: string | null
  destination_asset_id: string | null
  edge_id: string | null
  unexpected_observed: boolean
  anomalous_observed: boolean
  anomaly_score: number | null
  classification: string | null
  technique_ids: string[]
  synthetic: true
}

export interface TopologyPath {
  path_type: TopologyPathType
  ordered_node_ids: string[]
  ordered_edge_ids: string[]
  path_length: number
  evidence_source: string
  through_sequence_number: number | null
  hypothetical: boolean
  statement: string
  synthetic: true
}

export interface TopologyPathPage {
  items: TopologyPath[]
  total: number
  maximum_paths: number
  synthetic: true
}
