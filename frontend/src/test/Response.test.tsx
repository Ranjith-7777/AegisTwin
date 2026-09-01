import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ResponseCentrePage } from '../pages/ResponseCentrePage'
import * as detectionApi from '../services/detectionApi'
import * as responseApi from '../services/responseApi'
import * as simulationApi from '../services/simulationApi'
import type { ResponseAnalysisResult } from '../types/response'
import type { SimulationRun } from '../types/simulation'

vi.mock('../services/detectionApi')
vi.mock('../services/responseApi')
vi.mock('../services/simulationApi')

const run: SimulationRun = {
  simulation_run_id: 'run-1',
  scenario_id: 'staged-compromise-demo',
  seed: 1,
  start_time: '2026-07-22T00:00:00Z',
  playback_speed: 10,
  status: 'completed',
  event_count: 12,
  created_at: '2026-07-22T00:00:00Z',
}
const model = {
  model_id: 'model-1',
  model_type: 'IsolationForest',
  model_version: 'v2',
  feature_schema_version: 'v2',
  calibration_version: 'v2',
  calibration_method: 'ecdf',
  dataset_fingerprint: 'abc',
  random_state: 1,
  target_false_positive_rate: 0.1,
  calibrated_threshold: 0.9,
  threshold_percentile: 0.9,
  training_event_count: 10,
  validation_event_count: 5,
  created_at: '2026-07-22T00:00:00Z',
  synthetic: true,
  configuration_json: {},
}
const analysis: ResponseAnalysisResult = {
  response_analysis_id: 'analysis-1',
  run_id: 'run-1',
  model_id: 'model-1',
  incident_candidate_id: 'candidate-1',
  prediction_snapshot_id: 'prediction-1',
  through_sequence_number: 10,
  response_engine_version: 'v1',
  recommendation_count: 1,
  force_reanalyze: false,
  synthetic: true,
  created_at: '2026-07-22T00:00:00Z',
  recommendations: [
    {
      recommendation_id: 'recommendation-1',
      response_analysis_id: 'analysis-1',
      run_id: 'run-1',
      model_id: 'model-1',
      incident_candidate_id: 'candidate-1',
      prediction_snapshot_id: 'prediction-1',
      through_sequence_number: 10,
      playbook_id: 'block-synthetic-route',
      playbook_name: 'Block the network route',
      target_type: 'relationship',
      target_id: 'application-pod-01--cloud-database-01',
      rank: 1,
      recommendation_score: 0.81,
      component_scores: { evidence_applicability: 0.25 },
      penalties: { operational_disruption: 0.05 },
      defense_score: 0.62,
      defense_components: {
        security_improvement: 0.85,
        service_disruption: 0.12,
        resource_cost: 0.05,
        sla_penalty: 0.06,
        defense_score: 0.62,
      },
      defense_explanation:
        'Block the network route on application-pod-01--cloud-database-01: security improvement 0.85 less service disruption 0.12, resource cost 0.05 and SLA penalty 0.06 gives a Defense Score of 0.62.',
      required_approval_tier: 'analyst_approval',
      recommendation_state: 'simulation_complete',
      evidence_summary: ['Sequence-bounded evidence'],
      rationale: 'Relative ranking from synthetic evidence.',
      warnings: ['No action has been performed.'],
      synthetic: true,
      created_at: '2026-07-22T00:00:00Z',
      simulation: {
        simulation_id: 'simulation-1',
        recommendation_id: 'recommendation-1',
        run_id: 'run-1',
        through_sequence_number: 10,
        base_topology_version: 'v1',
        simulation_engine_version: 'v1',
        target_type: 'relationship',
        target_id: 'application-pod-01--cloud-database-01',
        changed_node_ids: [],
        changed_edge_ids: ['application-pod-01--cloud-database-01'],
        paths_before: [{}],
        paths_after: [],
        correlated_paths_interrupted: 1,
        predicted_paths_interrupted: 1,
        sensitive_assets_reachable_before: 2,
        sensitive_assets_reachable_after: 1,
        expected_relationships_affected: 1,
        affected_asset_count: 2,
        affected_edge_count: 1,
        interruption_score: 0.7,
        residual_exposure_score: 0.5,
        operational_disruption_score: 0.1,
        blast_radius: 'single_relationship',
        reversibility: 'reversible',
        approval_tier: 'analyst_approval',
        warnings: ['Clone only.'],
        synthetic: true,
        created_at: '2026-07-22T00:00:00Z',
      },
    },
  ],
}

beforeEach(() => {
  vi.mocked(simulationApi.getSimulationRuns).mockResolvedValue([run])
  vi.mocked(detectionApi.getDetectionModels).mockResolvedValue([model])
  vi.mocked(responseApi.getResponsePlaybooks).mockResolvedValue([])
  vi.mocked(responseApi.analyzeResponses).mockResolvedValue(analysis)
})

describe('Blue Agent response centre', () => {
  it('shows the safe empty state and submits a sequence-bounded analysis', async () => {
    render(<ResponseCentrePage />)
    expect(screen.getByText(/No real defensive action has been executed/)).toBeInTheDocument()
    await userEvent.selectOptions(await screen.findByLabelText('Response run'), 'run-1')
    await userEvent.selectOptions(screen.getByLabelText('Response model'), 'model-1')
    await userEvent.clear(screen.getByLabelText('Response through sequence'))
    await userEvent.type(screen.getByLabelText('Response through sequence'), '10')
    await userEvent.click(screen.getByRole('button', { name: 'Rank Mitigations' }))
    await waitFor(() => {
      expect(responseApi.analyzeResponses).toHaveBeenCalled()
    })
    expect(await screen.findByText('Block the network route')).toBeInTheDocument()
    expect(screen.getAllByLabelText('Defense score breakdown').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Security improvement').length).toBeGreaterThan(0)
    expect(screen.getAllByText('SLA penalty').length).toBeGreaterThan(0)
    expect(screen.getAllByText('0.620').length).toBeGreaterThan(0)
    expect(screen.getByText(/Approval: analyst approval/)).toBeInTheDocument()
    expect(screen.getByText(/Correlated paths interrupted: 1/)).toBeInTheDocument()
    expect(screen.getByText('Baseline synthetic topology')).toBeInTheDocument()
    expect(screen.getByText('Simulated post-response topology')).toBeInTheDocument()
    expect(screen.getByText(/heuristic simulation measures, not probabilities/)).toBeInTheDocument()
  })

  it('handles malformed response failures without crashing', async () => {
    vi.mocked(responseApi.analyzeResponses).mockRejectedValue(
      new Error('Malformed synthetic response analysis.'),
    )
    render(<ResponseCentrePage />)
    await userEvent.selectOptions(await screen.findByLabelText('Response run'), 'run-1')
    await userEvent.selectOptions(screen.getByLabelText('Response model'), 'model-1')
    await userEvent.click(screen.getByRole('button', { name: 'Rank Mitigations' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Malformed synthetic response analysis.',
    )
  })
})
