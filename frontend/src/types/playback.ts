import type { PlaybackState, SimulationRun, TelemetryEvent } from './simulation'
import type { AnomalyAssessment } from './detection'
import type { IncidentCandidate, TechniqueObservation } from './correlation'
import type { PredictionSnapshot } from './prediction'

export type PlaybackMessageType =
  | 'connection_ack'
  | 'playback_snapshot'
  | 'playback_started'
  | 'telemetry_event'
  | 'playback_paused'
  | 'playback_resumed'
  | 'playback_stopped'
  | 'playback_completed'
  | 'heartbeat'
  | 'detection_ready'
  | 'anomaly_assessment'
  | 'detection_warning'
  | 'detection_error'
  | 'correlation_ready'
  | 'mitre_technique_observation'
  | 'incident_candidate_update'
  | 'correlation_warning'
  | 'correlation_error'
  | 'prediction_ready'
  | 'next_stage_prediction'
  | 'prediction_warning'
  | 'prediction_error'
  | 'error'

export interface PlaybackEnvelope {
  message_type: PlaybackMessageType
  run_id: string
  sequence_number: number
  server_timestamp: string
  synthetic: true
  payload: Record<string, unknown>
}

export interface PlaybackSnapshotPayload {
  run: SimulationRun
  total_event_count: number
  starting_after_sequence: number
  playback_speed: number
  state: PlaybackState
  available_controls: string[]
}

export interface TelemetryEventPayload {
  event_index: number
  total_event_count: number
  event: TelemetryEvent
}

const MESSAGE_TYPES = new Set<PlaybackMessageType>([
  'connection_ack',
  'playback_snapshot',
  'playback_started',
  'telemetry_event',
  'playback_paused',
  'playback_resumed',
  'playback_stopped',
  'playback_completed',
  'heartbeat',
  'detection_ready',
  'anomaly_assessment',
  'detection_warning',
  'detection_error',
  'correlation_ready',
  'mitre_technique_observation',
  'incident_candidate_update',
  'correlation_warning',
  'correlation_error',
  'prediction_ready',
  'next_stage_prediction',
  'prediction_warning',
  'prediction_error',
  'error',
])

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

export function parsePlaybackEnvelope(value: unknown): PlaybackEnvelope | null {
  if (!isRecord(value) || typeof value.message_type !== 'string') return null
  if (!MESSAGE_TYPES.has(value.message_type as PlaybackMessageType)) return null
  if (
    typeof value.run_id !== 'string' ||
    typeof value.sequence_number !== 'number' ||
    value.sequence_number < 1 ||
    typeof value.server_timestamp !== 'string' ||
    value.synthetic !== true ||
    !isRecord(value.payload)
  ) {
    return null
  }
  if (value.message_type === 'telemetry_event') {
    const payload = value.payload
    if (
      typeof payload.event_index !== 'number' ||
      typeof payload.total_event_count !== 'number' ||
      !isRecord(payload.event) ||
      typeof payload.event.event_id !== 'string' ||
      !isRecord(payload.event.metadata) ||
      payload.event.metadata.synthetic !== true
    ) {
      return null
    }
  }
  if (value.message_type === 'anomaly_assessment' && !isAnomalyAssessment(value.payload)) {
    return null
  }
  if (
    value.message_type === 'mitre_technique_observation' &&
    !isTechniqueObservation(value.payload)
  )
    return null
  if (value.message_type === 'incident_candidate_update' && !isIncidentCandidate(value.payload))
    return null
  if (value.message_type === 'next_stage_prediction' && !isPredictionSnapshot(value.payload))
    return null
  return value as unknown as PlaybackEnvelope
}

function isPredictionSnapshot(
  value: Record<string, unknown>,
): value is Record<string, unknown> & PredictionSnapshot {
  return (
    typeof value.prediction_snapshot_id === 'string' &&
    typeof value.simulation_run_id === 'string' &&
    typeof value.model_id === 'string' &&
    typeof value.through_sequence_number === 'number' &&
    typeof value.predictor_version === 'string' &&
    typeof value.progression_catalogue_version === 'string' &&
    typeof value.prediction_state === 'string' &&
    typeof value.current_stage_estimate === 'string' &&
    typeof value.current_tactic_estimate === 'string' &&
    Array.isArray(value.observed_technique_ids) &&
    Array.isArray(value.observed_tactic_ids) &&
    Array.isArray(value.supporting_evidence) &&
    Array.isArray(value.hypotheses) &&
    value.hypotheses.every(
      (item) =>
        isRecord(item) &&
        typeof item.hypothesis_id === 'string' &&
        typeof item.rank === 'number' &&
        typeof item.hypothesis_type === 'string' &&
        typeof item.prediction_score === 'number' &&
        isRecord(item.component_scores) &&
        Array.isArray(item.prerequisite_evidence) &&
        Array.isArray(item.contradictory_evidence) &&
        typeof item.rationale === 'string' &&
        item.synthetic === true,
    ) &&
    value.synthetic === true
  )
}

export function getPredictionPayload(message: PlaybackEnvelope): PredictionSnapshot | null {
  return message.message_type === 'next_stage_prediction'
    ? (message.payload as unknown as PredictionSnapshot)
    : null
}

function isTechniqueObservation(
  value: Record<string, unknown>,
): value is Record<string, unknown> & TechniqueObservation {
  return (
    typeof value.mapping_id === 'string' &&
    typeof value.technique_id === 'string' &&
    typeof value.technique_name === 'string' &&
    typeof value.event_id === 'string' &&
    typeof value.sequence_number === 'number' &&
    typeof value.mapping_confidence === 'number' &&
    typeof value.rationale === 'string' &&
    typeof value.tactic === 'string' &&
    typeof value.mapper_version === 'string' &&
    typeof value.model_id === 'string' &&
    isRecord(value.evidence_fields) &&
    value.synthetic === true
  )
}
function isIncidentCandidate(
  value: Record<string, unknown>,
): value is Record<string, unknown> & IncidentCandidate {
  return (
    typeof value.incident_candidate_id === 'string' &&
    typeof value.simulation_run_id === 'string' &&
    typeof value.model_id === 'string' &&
    typeof value.title === 'string' &&
    typeof value.correlation_state === 'string' &&
    typeof value.priority === 'string' &&
    typeof value.correlation_score === 'number' &&
    isRecord(value.component_scores) &&
    typeof value.first_sequence_number === 'number' &&
    typeof value.latest_sequence_number === 'number' &&
    Array.isArray(value.involved_asset_ids) &&
    Array.isArray(value.observed_tactic_ids) &&
    Array.isArray(value.observed_technique_ids) &&
    typeof value.evidence_count === 'number' &&
    value.synthetic === true
  )
}
export function getTechniquePayload(message: PlaybackEnvelope): TechniqueObservation | null {
  return message.message_type === 'mitre_technique_observation'
    ? (message.payload as unknown as TechniqueObservation)
    : null
}
export function getIncidentPayload(message: PlaybackEnvelope): IncidentCandidate | null {
  return message.message_type === 'incident_candidate_update'
    ? (message.payload as unknown as IncidentCandidate)
    : null
}

function isAnomalyAssessment(
  value: Record<string, unknown>,
): value is Record<string, unknown> & AnomalyAssessment {
  return (
    typeof value.assessment_id === 'string' &&
    typeof value.model_id === 'string' &&
    typeof value.event_id === 'string' &&
    typeof value.sequence_number === 'number' &&
    typeof value.feature_schema_version === 'string' &&
    typeof value.calibration_method === 'string' &&
    typeof value.detector_type === 'string' &&
    typeof value.raw_isolation_forest_score === 'number' &&
    typeof value.isolation_forest_rank === 'number' &&
    typeof value.hybrid_anomaly_score === 'number' &&
    typeof value.threshold === 'number' &&
    (value.classification === 'normal' || value.classification === 'anomalous') &&
    Array.isArray(value.contributing_signals) &&
    value.contributing_signals.every((signal) => typeof signal === 'string') &&
    isRecord(value.component_scores) &&
    Object.values(value.component_scores).every((score) => typeof score === 'number') &&
    value.synthetic === true
  )
}

export function getAssessmentPayload(message: PlaybackEnvelope): AnomalyAssessment | null {
  return message.message_type === 'anomaly_assessment'
    ? (message.payload as unknown as AnomalyAssessment)
    : null
}

export function getTelemetryPayload(message: PlaybackEnvelope): TelemetryEventPayload | null {
  if (message.message_type !== 'telemetry_event') return null
  return message.payload as unknown as TelemetryEventPayload
}

export function getSnapshotPayload(message: PlaybackEnvelope): PlaybackSnapshotPayload | null {
  if (message.message_type !== 'playback_snapshot') return null
  const payload = message.payload
  if (
    !isRecord(payload.run) ||
    typeof payload.total_event_count !== 'number' ||
    typeof payload.starting_after_sequence !== 'number' ||
    typeof payload.playback_speed !== 'number' ||
    typeof payload.state !== 'string' ||
    !Array.isArray(payload.available_controls)
  ) {
    return null
  }
  return payload as unknown as PlaybackSnapshotPayload
}
