import type { IncidentCandidate, TechniqueObservation } from './correlation'
import type { AnomalyAssessment } from './detection'
import type { PredictionSnapshot } from './prediction'
import type { TelemetryEvent } from './simulation'
import type { RunTopologyState, TopologySnapshot } from './topology'

export interface LiveNodeState {
  asset_id: string
  observed: boolean
  anomalous_observed: boolean
  correlated: boolean
  predicted: boolean
  current_focus: boolean
  first_observed_sequence: number | null
  last_observed_sequence: number | null
  last_event_id: string | null
  anomaly_score: number | null
  classification: string | null
  observed_technique_ids: string[]
  event_count: number
  predicted_rank: number | null
  prediction_score: number | null
  prediction_rationale: string | null
  synthetic: true
}

export interface LiveEdgeState {
  edge_id: string
  source_asset_id: string
  destination_asset_id: string
  observed: boolean
  anomalous_observed: boolean
  correlated: boolean
  predicted: boolean
  unexpected: boolean
  current_focus: boolean
  first_observed_sequence: number | null
  last_observed_sequence: number | null
  associated_event_ids: string[]
  associated_technique_ids: string[]
  synthetic: true
}

export interface TopologyHistoryItem {
  sequence_number: number
  timestamp: string
  event_id: string
  source_asset_id: string | null
  destination_asset_id: string | null
  edge_id: string | null
  action: string
  anomaly_classification: string | null
  technique_ids: string[]
  candidate_state: string | null
  prediction_updated: boolean
  synthetic: true
}

export interface LiveTopologyOverlay {
  run_id: string | null
  model_id: string | null
  through_sequence_number: number
  known_asset_ids: string[]
  expected_edge_ids: string[]
  nodes: Record<string, LiveNodeState>
  edges: Record<string, LiveEdgeState>
  history: TopologyHistoryItem[]
  current_event: TelemetryEvent | null
  latest_incident: IncidentCandidate | null
  latest_prediction: PredictionSnapshot | null
  synthetic: true
}

export type LiveTopologyAction =
  | { type: 'configure'; topology: TopologySnapshot }
  | { type: 'start_run'; runId: string; modelId: string | null }
  | { type: 'telemetry'; event: TelemetryEvent; sequence: number }
  | { type: 'assessment'; assessment: AnomalyAssessment }
  | { type: 'technique'; observation: TechniqueObservation }
  | { type: 'correlation'; candidate: IncidentCandidate }
  | { type: 'prediction'; snapshot: PredictionSnapshot; topK: number }
  | { type: 'recover'; state: RunTopologyState }
  | { type: 'clear_transient' }
  | { type: 'reset' }

export function emptyLiveTopologyOverlay(): LiveTopologyOverlay {
  return {
    run_id: null,
    model_id: null,
    through_sequence_number: 0,
    known_asset_ids: [],
    expected_edge_ids: [],
    nodes: {},
    edges: {},
    history: [],
    current_event: null,
    latest_incident: null,
    latest_prediction: null,
    synthetic: true,
  }
}

function baseNode(asset_id: string): LiveNodeState {
  return {
    asset_id,
    observed: false,
    anomalous_observed: false,
    correlated: false,
    predicted: false,
    current_focus: false,
    first_observed_sequence: null,
    last_observed_sequence: null,
    last_event_id: null,
    anomaly_score: null,
    classification: null,
    observed_technique_ids: [],
    event_count: 0,
    predicted_rank: null,
    prediction_score: null,
    prediction_rationale: null,
    synthetic: true,
  }
}

function baseEdge(edge_id: string): LiveEdgeState {
  const [source_asset_id = '', destination_asset_id = ''] = edge_id.split('--', 2)
  return {
    edge_id,
    source_asset_id,
    destination_asset_id,
    observed: false,
    anomalous_observed: false,
    correlated: false,
    predicted: false,
    unexpected: false,
    current_focus: false,
    first_observed_sequence: null,
    last_observed_sequence: null,
    associated_event_ids: [],
    associated_technique_ids: [],
    synthetic: true,
  }
}

function updateHistory(
  state: LiveTopologyOverlay,
  eventId: string,
  update: Partial<TopologyHistoryItem>,
) {
  return state.history.map((item) => (item.event_id === eventId ? { ...item, ...update } : item))
}

export function liveTopologyReducer(
  state: LiveTopologyOverlay,
  action: LiveTopologyAction,
): LiveTopologyOverlay {
  if (action.type === 'reset')
    return {
      ...emptyLiveTopologyOverlay(),
      known_asset_ids: state.known_asset_ids,
      expected_edge_ids: state.expected_edge_ids,
    }
  if (action.type === 'configure')
    return {
      ...state,
      known_asset_ids: action.topology.nodes.map((item) => item.asset_id),
      expected_edge_ids: action.topology.edges.map((item) => item.edge_id),
    }
  if (action.type === 'start_run')
    return {
      ...emptyLiveTopologyOverlay(),
      known_asset_ids: state.known_asset_ids,
      expected_edge_ids: state.expected_edge_ids,
      run_id: action.runId,
      model_id: action.modelId,
    }
  if (action.type === 'clear_transient')
    return {
      ...state,
      current_event: null,
      nodes: Object.fromEntries(
        Object.entries(state.nodes).map(([id, item]) => [id, { ...item, current_focus: false }]),
      ),
      edges: Object.fromEntries(
        Object.entries(state.edges).map(([id, item]) => [id, { ...item, current_focus: false }]),
      ),
    }
  if (action.type === 'telemetry') {
    if (
      action.sequence <= state.through_sequence_number ||
      (state.run_id && action.event.simulation_run_id !== state.run_id)
    )
      return state
    const known = new Set(state.known_asset_ids)
    const source = known.has(action.event.source_id) ? action.event.source_id : null
    const destination =
      action.event.destination_id && known.has(action.event.destination_id)
        ? action.event.destination_id
        : null
    const edgeId = source && destination ? `${source}--${destination}` : null
    const expected = edgeId ? state.expected_edge_ids.includes(edgeId) : false
    const nodes: Record<string, LiveNodeState> = Object.fromEntries(
      Object.entries(state.nodes).map(([id, item]) => [id, { ...item, current_focus: false }]),
    )
    for (const id of [source, destination])
      if (id) {
        const item = nodes[id] ?? baseNode(id)
        nodes[id] = {
          ...item,
          observed: true,
          current_focus: true,
          first_observed_sequence: item.first_observed_sequence ?? action.sequence,
          last_observed_sequence: action.sequence,
          last_event_id: action.event.event_id,
          event_count: item.event_count + 1,
        }
      }
    const edges: Record<string, LiveEdgeState> = Object.fromEntries(
      Object.entries(state.edges).map(([id, item]) => [id, { ...item, current_focus: false }]),
    )
    if (edgeId) {
      const item = edges[edgeId] ?? baseEdge(edgeId)
      edges[edgeId] = {
        ...item,
        observed: true,
        unexpected: !expected,
        current_focus: true,
        first_observed_sequence: item.first_observed_sequence ?? action.sequence,
        last_observed_sequence: action.sequence,
        associated_event_ids: item.associated_event_ids.includes(action.event.event_id)
          ? item.associated_event_ids
          : [...item.associated_event_ids, action.event.event_id],
      }
    }
    return {
      ...state,
      nodes,
      edges,
      through_sequence_number: action.sequence,
      current_event: action.event,
      history: [
        ...state.history,
        {
          sequence_number: action.sequence,
          timestamp: action.event.timestamp,
          event_id: action.event.event_id,
          source_asset_id: source,
          destination_asset_id: destination,
          edge_id: edgeId,
          action: action.event.action,
          anomaly_classification: null,
          technique_ids: [],
          candidate_state: null,
          prediction_updated: false,
          synthetic: true,
        },
      ],
    }
  }
  if (action.type === 'assessment') {
    const historyItem = state.history.find((item) => item.event_id === action.assessment.event_id)
    if (!historyItem) return state
    const anomalous = action.assessment.classification === 'anomalous'
    const nodes = { ...state.nodes }
    for (const id of [historyItem.source_asset_id, historyItem.destination_asset_id])
      if (id && nodes[id])
        nodes[id] = {
          ...nodes[id],
          anomalous_observed: nodes[id].anomalous_observed || anomalous,
          anomaly_score: action.assessment.hybrid_anomaly_score,
          classification: action.assessment.classification,
        }
    const edges = { ...state.edges }
    const assessedEdge = historyItem.edge_id ? edges[historyItem.edge_id] : undefined
    if (historyItem.edge_id && assessedEdge)
      edges[historyItem.edge_id] = {
        ...assessedEdge,
        anomalous_observed: assessedEdge.anomalous_observed || anomalous,
      }
    return {
      ...state,
      nodes,
      edges,
      history: updateHistory(state, action.assessment.event_id, {
        anomaly_classification: action.assessment.classification,
      }),
    }
  }
  if (action.type === 'technique') {
    const historyItem = state.history.find((item) => item.event_id === action.observation.event_id)
    if (!historyItem) return state
    const nodes = { ...state.nodes }
    for (const id of [historyItem.source_asset_id, historyItem.destination_asset_id])
      if (id && nodes[id])
        nodes[id] = {
          ...nodes[id],
          observed_technique_ids: [
            ...new Set([...nodes[id].observed_technique_ids, action.observation.technique_id]),
          ],
        }
    const edges = { ...state.edges }
    const techniqueEdge = historyItem.edge_id ? edges[historyItem.edge_id] : undefined
    if (historyItem.edge_id && techniqueEdge)
      edges[historyItem.edge_id] = {
        ...techniqueEdge,
        associated_technique_ids: [
          ...new Set([...techniqueEdge.associated_technique_ids, action.observation.technique_id]),
        ],
      }
    return {
      ...state,
      nodes,
      edges,
      history: updateHistory(state, action.observation.event_id, {
        technique_ids: [
          ...new Set([...historyItem.technique_ids, action.observation.technique_id]),
        ],
      }),
    }
  }
  if (action.type === 'correlation') {
    const nodes: Record<string, LiveNodeState> = Object.fromEntries(
      Object.entries(state.nodes).map(([id, item]) => [
        id,
        { ...item, correlated: action.candidate.involved_asset_ids.includes(id) },
      ]),
    )
    const edges: Record<string, LiveEdgeState> = Object.fromEntries(
      Object.entries(state.edges).map(([id, item]) => [
        id,
        {
          ...item,
          correlated:
            item.observed &&
            action.candidate.involved_asset_ids.includes(item.source_asset_id) &&
            action.candidate.involved_asset_ids.includes(item.destination_asset_id),
        },
      ]),
    )
    const latest = state.history.at(-1)
    return {
      ...state,
      nodes,
      edges,
      latest_incident: action.candidate,
      history: latest
        ? updateHistory(state, latest.event_id, {
            candidate_state: action.candidate.correlation_state,
          })
        : state.history,
    }
  }
  if (action.type === 'prediction') {
    const nodes: Record<string, LiveNodeState> = Object.fromEntries(
      Object.entries(state.nodes).map(([id, item]) => [
        id,
        {
          ...item,
          predicted: false,
          predicted_rank: null,
          prediction_score: null,
          prediction_rationale: null,
        },
      ]),
    )
    const edges: Record<string, LiveEdgeState> = Object.fromEntries(
      Object.entries(state.edges).map(([id, item]) => [id, { ...item, predicted: false }]),
    )
    const current = state.current_event?.destination_id ?? state.current_event?.source_id
    const hypotheses = action.snapshot.hypotheses
      .filter((item) => item.hypothesis_type === 'next_asset' && item.predicted_asset_id)
      .slice(0, action.topK)
    for (const item of hypotheses) {
      const id = item.predicted_asset_id
      if (!id || !state.known_asset_ids.includes(id)) continue
      const node = nodes[id] ?? baseNode(id)
      nodes[id] = {
        ...node,
        predicted: true,
        predicted_rank: item.rank,
        prediction_score: item.prediction_score,
        prediction_rationale: item.rationale,
      }
      if (current) {
        const edgeId = `${current}--${id}`
        const edge = edges[edgeId] ?? baseEdge(edgeId)
        edges[edgeId] = { ...edge, predicted: true }
      }
    }
    const latest = state.history.at(-1)
    return {
      ...state,
      nodes,
      edges,
      latest_prediction: action.snapshot,
      history: latest
        ? updateHistory(state, latest.event_id, { prediction_updated: true })
        : state.history,
    }
  }
  let recovered: LiveTopologyOverlay = {
    ...emptyLiveTopologyOverlay(),
    known_asset_ids: state.known_asset_ids,
    expected_edge_ids: state.expected_edge_ids,
    run_id: action.state.simulation_run_id,
    model_id: action.state.model_id,
    // Rebuild causally from zero; pre-seeding the final limit would make the
    // normal telemetry guard reject every recovered mapping as a duplicate.
    through_sequence_number: 0,
  }
  for (const mapping of action.state.event_mappings)
    recovered = liveTopologyReducer(recovered, {
      type: 'telemetry',
      sequence: mapping.sequence_number,
      event: {
        event_id: mapping.event_id,
        scenario_id: 'recovered-synthetic-state',
        simulation_run_id: action.state.simulation_run_id,
        timestamp: '',
        event_type: 'session',
        action: 'access',
        outcome: 'allowed',
        severity: 'informational',
        source_type: 'service',
        source_id: mapping.source_asset_id ?? 'unknown-synthetic-id',
        destination_id: mapping.destination_asset_id,
        user_id: null,
        device_id: null,
        source_ip: null,
        destination_ip: null,
        privilege_level: null,
        failed_attempts: 0,
        bytes_transferred: 0,
        process_name: null,
        metadata: { synthetic: true },
        created_at: '',
      },
    })
  return {
    ...recovered,
    through_sequence_number: action.state.current_sequence_limit,
    current_event: null,
    nodes: Object.fromEntries(
      Object.entries(recovered.nodes).map(([id, item]) => [
        id,
        {
          ...item,
          current_focus: false,
          anomalous_observed: action.state.anomalous_observed_asset_ids.includes(id),
          correlated: action.state.correlated_asset_ids.includes(id),
          predicted: action.state.predicted_asset_ids.includes(id),
        },
      ]),
    ),
    edges: Object.fromEntries(
      Object.entries(recovered.edges).map(([id, item]) => [
        id,
        {
          ...item,
          current_focus: false,
          anomalous_observed: action.state.anomalous_observed_edge_ids.includes(id),
          correlated: action.state.correlated_edge_ids.includes(id),
          predicted: action.state.predicted_edge_ids.includes(id),
          unexpected: action.state.unexpected_observed_edge_ids.includes(id),
        },
      ]),
    ),
  }
}
