import { apiClient } from './apiClient'
import type {
  InfrastructureEdge,
  InfrastructureNode,
  RunTopologyState,
  TopologyPath,
  TopologyPathPage,
  TopologyPathType,
  TopologySnapshot,
} from '../types/topology'

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function node(value: unknown): value is InfrastructureNode {
  return (
    record(value) &&
    typeof value.asset_id === 'string' &&
    typeof value.display_name === 'string' &&
    typeof value.asset_type === 'string' &&
    typeof value.zone === 'string' &&
    typeof value.sensitivity === 'string' &&
    typeof value.criticality === 'string' &&
    typeof value.description === 'string' &&
    value.synthetic === true &&
    record(value.metadata)
  )
}

function edge(value: unknown): value is InfrastructureEdge {
  return (
    record(value) &&
    typeof value.edge_id === 'string' &&
    typeof value.source_asset_id === 'string' &&
    typeof value.destination_asset_id === 'string' &&
    typeof value.relationship_type === 'string' &&
    typeof value.permitted === 'boolean' &&
    value.direction === 'directed' &&
    value.synthetic === true
  )
}

export function parseTopologySnapshot(value: unknown): TopologySnapshot | null {
  return record(value) &&
    typeof value.topology_version === 'string' &&
    Array.isArray(value.nodes) &&
    value.nodes.every(node) &&
    Array.isArray(value.edges) &&
    value.edges.every(edge) &&
    typeof value.generated_at === 'string' &&
    value.synthetic === true
    ? (value as unknown as TopologySnapshot)
    : null
}

function stringList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

export function parseRunTopologyState(value: unknown): RunTopologyState | null {
  return record(value) &&
    typeof value.simulation_run_id === 'string' &&
    (value.model_id === null || typeof value.model_id === 'string') &&
    stringList(value.observed_asset_ids) &&
    stringList(value.observed_edge_ids) &&
    stringList(value.correlated_asset_ids) &&
    stringList(value.correlated_edge_ids) &&
    stringList(value.predicted_asset_ids) &&
    stringList(value.predicted_edge_ids) &&
    typeof value.current_sequence_limit === 'number' &&
    value.synthetic === true
    ? (value as unknown as RunTopologyState)
    : null
}

function path(value: unknown): value is TopologyPath {
  return (
    record(value) &&
    ['expected', 'observed', 'correlated', 'predicted'].includes(String(value.path_type)) &&
    stringList(value.ordered_node_ids) &&
    stringList(value.ordered_edge_ids) &&
    typeof value.path_length === 'number' &&
    typeof value.evidence_source === 'string' &&
    typeof value.hypothetical === 'boolean' &&
    typeof value.statement === 'string' &&
    value.synthetic === true
  )
}

export function parseTopologyPathPage(value: unknown): TopologyPathPage | null {
  return record(value) &&
    Array.isArray(value.items) &&
    value.items.every(path) &&
    typeof value.total === 'number' &&
    typeof value.maximum_paths === 'number' &&
    value.synthetic === true
    ? (value as unknown as TopologyPathPage)
    : null
}

export async function getTopology(): Promise<TopologySnapshot> {
  const parsed = parseTopologySnapshot((await apiClient.get('/api/v1/topology')).data)
  if (!parsed) throw new Error('Malformed synthetic topology response.')
  return parsed
}

export async function getRunTopologyState(
  runId: string,
  modelId: string | undefined,
  throughSequence: number,
): Promise<RunTopologyState> {
  const parsed = parseRunTopologyState(
    (
      await apiClient.get(`/api/v1/topology/runs/${encodeURIComponent(runId)}/state`, {
        params: { model_id: modelId, through_sequence_number: throughSequence },
      })
    ).data,
  )
  if (!parsed) throw new Error('Malformed synthetic run topology response.')
  return parsed
}

export async function getTopologyPaths(input: {
  source: string
  destination: string
  pathType: TopologyPathType
  runId?: string
  modelId?: string
  throughSequence?: number
}): Promise<TopologyPathPage> {
  const parsed = parseTopologyPathPage(
    (
      await apiClient.get('/api/v1/topology/paths', {
        params: {
          source_asset_id: input.source,
          destination_asset_id: input.destination,
          path_type: input.pathType,
          simulation_run_id: input.runId,
          model_id: input.modelId,
          through_sequence_number: input.throughSequence,
        },
      })
    ).data,
  )
  if (!parsed) throw new Error('Malformed synthetic topology path response.')
  return parsed
}
