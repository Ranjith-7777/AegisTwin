import { describe, expect, it } from 'vitest'

import { emptyLiveTopologyOverlay, liveTopologyReducer } from '../types/liveTopology'
import type { AnomalyAssessment } from '../types/detection'
import type { TechniqueObservation } from '../types/correlation'
import type { TelemetryEvent } from '../types/simulation'
import type { RunTopologyState, TopologySnapshot } from '../types/topology'

const topology: TopologySnapshot = {
  topology_version: 'aegistwin-synthetic-topology-v1',
  nodes: ['employee-laptop-01', 'authentication-server-01', 'application-server-01'].map(
    (asset_id) => ({
      asset_id,
      display_name: asset_id,
      asset_type: 'endpoint',
      zone: 'user_zone',
      sensitivity: 'internal',
      criticality: 'low',
      description: 'Synthetic test asset.',
      synthetic: true,
      metadata: {},
    }),
  ),
  edges: [
    {
      edge_id: 'employee-laptop-01--authentication-server-01',
      source_asset_id: 'employee-laptop-01',
      destination_asset_id: 'authentication-server-01',
      relationship_type: 'expected_relationship',
      protocol_label: 'HTTPS',
      direction: 'directed',
      permitted: true,
      trust_level: 'standard',
      synthetic: true,
      metadata: {},
    },
  ],
  generated_at: '2026-07-22T00:00:00Z',
  synthetic: true,
}

function event(sequence: number, destination = 'authentication-server-01'): TelemetryEvent {
  return {
    event_id: `event-${String(sequence)}`,
    scenario_id: 'synthetic',
    simulation_run_id: 'run-1',
    timestamp: `2026-07-22T00:00:0${String(sequence)}Z`,
    event_type: 'authentication',
    action: 'login',
    outcome: 'success',
    severity: 'medium',
    source_type: 'device',
    source_id: 'employee-laptop-01',
    destination_id: destination,
    user_id: null,
    device_id: null,
    source_ip: null,
    destination_ip: null,
    privilege_level: null,
    failed_attempts: 0,
    bytes_transferred: 0,
    process_name: null,
    metadata: { synthetic: true },
    created_at: '2026-07-22T00:00:00Z',
  }
}

function configured() {
  const initial = liveTopologyReducer(emptyLiveTopologyOverlay(), { type: 'configure', topology })
  return liveTopologyReducer(initial, { type: 'start_run', runId: 'run-1', modelId: 'model-1' })
}

describe('live topology reducer', () => {
  it('adds observed paths incrementally without accepting duplicate or future state', () => {
    const first = liveTopologyReducer(configured(), {
      type: 'telemetry',
      event: event(1),
      sequence: 1,
    })
    expect(first.nodes['employee-laptop-01']?.current_focus).toBe(true)
    expect(first.edges['employee-laptop-01--authentication-server-01']?.observed).toBe(true)
    expect(first.nodes['application-server-01']).toBeUndefined()
    const duplicate = liveTopologyReducer(first, {
      type: 'telemetry',
      event: event(1),
      sequence: 1,
    })
    expect(duplicate.history).toHaveLength(1)
  })

  it('marks only the matching event path anomalous and attaches observed techniques', () => {
    let state = liveTopologyReducer(configured(), {
      type: 'telemetry',
      event: event(1),
      sequence: 1,
    })
    const assessment: AnomalyAssessment = {
      assessment_id: 'assessment-1',
      model_id: 'model-1',
      event_id: 'event-1',
      sequence_number: 1,
      feature_schema_version: 'v2',
      calibration_method: 'synthetic',
      detector_type: 'hybrid',
      raw_isolation_forest_score: 0.2,
      isolation_forest_rank: 0.8,
      hybrid_anomaly_score: 0.91,
      threshold: 0.7,
      classification: 'anomalous',
      contributing_signals: ['synthetic deviation'],
      component_scores: {
        isolation_forest: 0.8,
        robust_numerical_deviation: 0.7,
        categorical_rarity: 0.6,
        behavioural_transition_rarity: 0.5,
        infrastructure_novelty: 0.4,
      },
      synthetic: true,
    }
    state = liveTopologyReducer(state, { type: 'assessment', assessment })
    const observation: TechniqueObservation = {
      mapping_id: 'mapping-1',
      technique_id: 'T1078',
      technique_name: 'Valid Accounts',
      event_id: 'event-1',
      sequence_number: 1,
      mapping_confidence: 0.8,
      evidence_fields: {},
      rationale: 'Synthetic mapping.',
      tactic: 'Initial Access',
      mapper_version: 'v1',
      model_id: 'model-1',
      synthetic: true,
    }
    state = liveTopologyReducer(state, { type: 'technique', observation })
    expect(state.nodes['authentication-server-01']?.anomalous_observed).toBe(true)
    expect(state.nodes['authentication-server-01']?.anomaly_score).toBe(0.91)
    expect(
      state.edges['employee-laptop-01--authentication-server-01']?.associated_technique_ids,
    ).toEqual(['T1078'])
  })

  it('represents known but unsupported relationships conservatively and ignores unknown assets', () => {
    const unexpected = liveTopologyReducer(configured(), {
      type: 'telemetry',
      event: event(1, 'application-server-01'),
      sequence: 1,
    })
    expect(unexpected.edges['employee-laptop-01--application-server-01']?.unexpected).toBe(true)
    const unknown = liveTopologyReducer(unexpected, {
      type: 'telemetry',
      event: event(2, 'unknown-device'),
      sequence: 2,
    })
    expect(unknown.nodes['unknown-device']).toBeUndefined()
    expect(unknown.history).toHaveLength(2)
  })

  it('clears transient focus without erasing accumulated evidence', () => {
    const observed = liveTopologyReducer(configured(), {
      type: 'telemetry',
      event: event(1),
      sequence: 1,
    })
    const cleared = liveTopologyReducer(observed, { type: 'clear_transient' })
    expect(cleared.nodes['employee-laptop-01']?.current_focus).toBe(false)
    expect(cleared.nodes['employee-laptop-01']?.observed).toBe(true)
  })

  it('reconstructs the authoritative sequence without dropping recovered mappings', () => {
    const recoveredState: RunTopologyState = {
      state_version: 'live-topology-state-v1',
      simulation_run_id: 'run-1',
      model_id: 'model-1',
      current_sequence_limit: 1,
      observed_asset_ids: ['employee-laptop-01', 'authentication-server-01'],
      observed_edge_ids: ['employee-laptop-01--authentication-server-01'],
      anomalous_observed_asset_ids: ['authentication-server-01'],
      anomalous_observed_edge_ids: ['employee-laptop-01--authentication-server-01'],
      unexpected_observed_edge_ids: [],
      correlated_asset_ids: [],
      correlated_edge_ids: [],
      predicted_asset_ids: [],
      predicted_edge_ids: [],
      event_mappings: [
        {
          event_id: 'event-1',
          sequence_number: 1,
          source_asset_id: 'employee-laptop-01',
          destination_asset_id: 'authentication-server-01',
          edge_id: 'employee-laptop-01--authentication-server-01',
          unexpected_observed: false,
          anomalous_observed: true,
          anomaly_score: 0.91,
          classification: 'anomalous',
          technique_ids: ['T1078'],
          synthetic: true,
        },
      ],
      predicted_paths: [],
      synthetic: true,
    }
    const recovered = liveTopologyReducer(configured(), {
      type: 'recover',
      state: recoveredState,
    })
    expect(recovered.through_sequence_number).toBe(1)
    expect(recovered.history).toHaveLength(1)
    expect(recovered.edges['employee-laptop-01--authentication-server-01']?.observed).toBe(true)
    expect(recovered.nodes['authentication-server-01']?.anomalous_observed).toBe(true)
  })
})
