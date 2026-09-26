import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { LivePredictionDashboard } from '../components/prediction/LivePredictionDashboard'
import { getPredictionPayload, parsePlaybackEnvelope } from '../types/playback'
import type { PredictionSnapshot } from '../types/prediction'

const snapshot: PredictionSnapshot = {
  prediction_snapshot_id: 'snapshot-1',
  simulation_run_id: 'run-1',
  model_id: 'model-1',
  incident_candidate_id: 'candidate-1',
  through_sequence_number: 5,
  predictor_version: 'hybrid-progression-v1',
  progression_catalogue_version: 'aegistwin-progression-v1',
  prediction_state: 'active',
  current_stage_estimate: 'authentication_pressure',
  current_tactic_estimate: 'Credential Access',
  observed_technique_ids: ['T1110.001'],
  observed_tactic_ids: ['Credential Access'],
  candidate_hypothesis_count: 1,
  insufficient_evidence_reason: null,
  supporting_evidence: ['observed technique T1110.001'],
  hypotheses: [
    {
      hypothesis_id: 'hypothesis-1',
      prediction_snapshot_id: 'snapshot-1',
      rank: 1,
      hypothesis_type: 'next_technique',
      predicted_technique_id: 'T1078',
      predicted_technique_name: 'Valid Accounts',
      predicted_tactic: 'Initial Access',
      predicted_asset_id: null,
      predicted_objective: null,
      prediction_score: 0.71,
      component_scores: { technique_transition: 0.9, contradiction_penalty: 0 },
      prerequisite_evidence: ['synthetic authentication pressure'],
      contradictory_evidence: [],
      rationale: 'Ranked from the local progression graph.',
      synthetic: true,
    },
  ],
  synthetic: true,
  created_at: '2026-07-22T00:00:00Z',
}

describe('next-stage prediction', () => {
  it('strictly parses a causal prediction envelope', () => {
    const envelope = parsePlaybackEnvelope({
      message_type: 'next_stage_prediction',
      run_id: 'run-1',
      sequence_number: 9,
      server_timestamp: '2026-07-22T00:00:00Z',
      synthetic: true,
      payload: snapshot,
    })
    expect(envelope).not.toBeNull()
    if (!envelope) throw new Error('Expected a valid prediction envelope.')
    expect(getPredictionPayload(envelope)).toEqual(snapshot)
    expect(parsePlaybackEnvelope({ ...envelope, payload: { synthetic: true } })).toBeNull()
  })

  it('renders ranked hypotheses as cautious synthetic evidence', () => {
    render(<LivePredictionDashboard current={snapshot} timeline={[snapshot]} />)
    expect(screen.getByText(/#1 T1078/)).toBeInTheDocument()
    expect(screen.getByText(/not probabilities, certainty/i)).toBeInTheDocument()
    expect(screen.getAllByText(/authentication_pressure/)).toHaveLength(2)
  })
})
