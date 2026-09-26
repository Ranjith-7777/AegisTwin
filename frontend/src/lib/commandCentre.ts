import type { IncidentCandidate } from '../types/correlation'
import type { LiveTopologyOverlay } from '../types/liveTopology'
import type { PredictionSnapshot } from '../types/prediction'
import type { PlaybackState } from '../types/simulation'
import type { TopologySnapshot } from '../types/topology'

/**
 * Every figure below is derived from persisted synthetic evidence that the range has
 * actually produced. Nothing here is a fixed demonstration value.
 */

export type CloudHealth = 'healthy' | 'degraded' | 'under attack' | 'mitigated'
export type AgentState = 'idle' | 'standby' | 'active' | 'complete'

/** Zones on the synthetic request-serving path, used for availability accounting. */
const SERVING_ZONES = new Set(['edge_zone', 'cluster_zone', 'workload_zone', 'data_zone'])
const POD_ASSET_TYPE = 'kubernetes_pod'

export interface CommandCentreInput {
  topology: TopologySnapshot | null
  live: LiveTopologyOverlay
  playbackState: PlaybackState
  hasActiveRun: boolean
  incident: IncidentCandidate | null
  prediction: PredictionSnapshot | null
  mitigatedNodeIds: string[]
  hasRecommendation: boolean
}

export interface CommandCentreState {
  cloudHealth: CloudHealth
  riskScore: number
  riskBasis: string
  availabilityPercent: number
  servingRelationships: number
  impairedRelationships: number
  runningPodReplicas: number
  totalPodReplicas: number
  degradedNodeIds: string[]
  attackEdgeIds: string[]
  predictedEdgeIds: string[]
  activeIncidents: number
  redAgentState: AgentState
  redAgentDetail: string
  blueAgentState: AgentState
  blueAgentDetail: string
}

function replicasOf(metadata: Record<string, unknown>): number {
  const value = metadata.replicas
  return typeof value === 'number' && Number.isFinite(value) ? value : 1
}

function clamp(value: number, low: number, high: number) {
  return Math.min(high, Math.max(low, value))
}

export function deriveCommandCentreState(input: CommandCentreInput): CommandCentreState {
  const { topology, live, incident, prediction, mitigatedNodeIds } = input
  const nodes = topology?.nodes ?? []
  const edges = topology?.edges ?? []
  const zoneOf = new Map(nodes.map((node) => [node.asset_id, node.zone]))
  const mitigated = new Set(mitigatedNodeIds)

  const degradedNodeIds = Object.values(live.nodes)
    .filter((node) => node.anomalous_observed && !mitigated.has(node.asset_id))
    .map((node) => node.asset_id)
    .sort()
  const degraded = new Set(degradedNodeIds)
  const attackEdgeIds = Object.values(live.edges)
    .filter((edge) => edge.observed && (edge.anomalous_observed || edge.unexpected))
    .map((edge) => edge.edge_id)
    .sort()
  const predictedEdgeIds = Object.values(live.edges)
    .filter((edge) => edge.predicted)
    .map((edge) => edge.edge_id)
    .sort()

  // Availability: the share of expected serving-path relationships that carry no
  // anomalous, unexpected or degraded-endpoint evidence.
  const servingEdges = edges.filter(
    (edge) =>
      SERVING_ZONES.has(zoneOf.get(edge.source_asset_id) ?? '') &&
      SERVING_ZONES.has(zoneOf.get(edge.destination_asset_id) ?? ''),
  )
  const impaired = servingEdges.filter((edge) => {
    const liveEdge = live.edges[edge.edge_id]
    const endpointDegraded =
      degraded.has(edge.source_asset_id) || degraded.has(edge.destination_asset_id)
    return (
      endpointDegraded ||
      Boolean(liveEdge?.observed && (liveEdge.anomalous_observed || liveEdge.unexpected))
    )
  })
  const availabilityPercent = servingEdges.length
    ? Math.round(((servingEdges.length - impaired.length) / servingEdges.length) * 1000) / 10
    : 100

  const podNodes = nodes.filter((node) => node.asset_type === POD_ASSET_TYPE)
  const totalPodReplicas = podNodes.reduce((total, node) => total + replicasOf(node.metadata), 0)
  const runningPodReplicas = podNodes
    .filter((node) => !degraded.has(node.asset_id))
    .reduce((total, node) => total + replicasOf(node.metadata), 0)

  // Risk: anomaly strength, correlation confidence, prediction confidence and
  // whether traffic left the expected architecture.
  const peakAnomaly = Object.values(live.nodes).reduce(
    (peak, node) => Math.max(peak, node.anomaly_score ?? 0),
    0,
  )
  const topPrediction = prediction?.hypotheses[0]?.prediction_score ?? 0
  const unexpectedPresent = Object.values(live.edges).some(
    (edge) => edge.observed && edge.unexpected,
  )
  const riskScore = Math.round(
    clamp(
      peakAnomaly * 40 +
        (incident?.correlation_score ?? 0) * 30 +
        topPrediction * 20 +
        (unexpectedPresent ? 10 : 0),
      0,
      100,
    ),
  )
  const riskBasis = input.hasActiveRun
    ? `peak anomaly ${peakAnomaly.toFixed(2)} · correlation ${(incident?.correlation_score ?? 0).toFixed(2)} · prediction ${topPrediction.toFixed(2)}`
    : 'no synthetic evidence replayed yet'

  const cloudHealth: CloudHealth =
    attackEdgeIds.length > 0
      ? 'under attack'
      : degradedNodeIds.length > 0
        ? 'degraded'
        : mitigated.size > 0
          ? 'mitigated'
          : 'healthy'

  const redAgentState: AgentState = !input.hasActiveRun
    ? 'idle'
    : input.playbackState === 'completed'
      ? 'complete'
      : 'active'
  const redAgentDetail = input.hasActiveRun
    ? `${input.playbackState} · sequence ${String(live.through_sequence_number)}`
    : 'awaiting scenario selection'

  const blueAgentState: AgentState = input.hasRecommendation
    ? 'active'
    : incident
      ? 'standby'
      : input.hasActiveRun
        ? 'standby'
        : 'idle'
  const blueAgentDetail = input.hasRecommendation
    ? 'ranked mitigations available'
    : incident
      ? 'incident correlated · ready to rank mitigations'
      : input.hasActiveRun
        ? 'observing synthetic evidence'
        : 'awaiting synthetic evidence'

  return {
    cloudHealth,
    riskScore,
    riskBasis,
    availabilityPercent,
    servingRelationships: servingEdges.length,
    impairedRelationships: impaired.length,
    runningPodReplicas,
    totalPodReplicas,
    degradedNodeIds,
    attackEdgeIds,
    predictedEdgeIds,
    activeIncidents: incident ? 1 : 0,
    redAgentState,
    redAgentDetail,
    blueAgentState,
    blueAgentDetail,
  }
}
