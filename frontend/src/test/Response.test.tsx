import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ResponsePlansPage } from '../pages/blueAgent/ResponsePlansPage'
import * as bluePlanningApi from '../services/bluePlanningApi'
import * as correlationApi from '../services/correlationApi'
import * as detectionApi from '../services/detectionApi'
import * as responseApi from '../services/responseApi'
import * as simulationApi from '../services/simulationApi'
import type { PlanComparisonResult } from '../types/bluePlanning'
import type { IncidentPage } from '../types/correlation'
import type { ResponseAnalysisResult } from '../types/response'
import type { SimulationRun } from '../types/simulation'

vi.mock('../services/detectionApi')
vi.mock('../services/responseApi')
vi.mock('../services/simulationApi')
vi.mock('../services/bluePlanningApi')
vi.mock('../services/correlationApi')

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
const incidents: IncidentPage = {
  items: [
    {
      incident_candidate_id: 'candidate-1',
      simulation_run_id: 'run-1',
      model_id: 'model-1',
      title: 'Staged compromise incident',
      correlation_state: 'high_priority',
      priority: 'high',
      correlation_score: 0.9,
      component_scores: {},
      first_sequence_number: 1,
      latest_sequence_number: 10,
      primary_user_id: null,
      primary_device_id: null,
      involved_asset_ids: [],
      observed_tactic_ids: [],
      observed_technique_ids: [],
      evidence_count: 3,
      synthetic: true,
    },
  ],
  page: 1,
  page_size: 20,
  total: 1,
  pages: 1,
}
const comparison: PlanComparisonResult = {
  simulation_run_id: 'run-1',
  model_id: 'model-1',
  incident_candidate_id: 'candidate-1',
  through_sequence_number: 10,
  autonomy_mode: 'recommend',
  recommended_recommendation_id: 'recommendation-1',
  candidates: [
    {
      recommendation_id: 'recommendation-1',
      playbook_id: 'block-synthetic-route',
      playbook_name: 'Block the network route',
      action_type: 'edge_restriction',
      target_type: 'relationship',
      target_id: 'application-pod-01--cloud-database-01',
      required_approval_tier: 'analyst_approval',
      reversibility: 'reversible',
      operational_impact: 'medium',
      security_gain_evidence: {
        attack_paths_before: 2,
        attack_paths_after: 1,
        top_attack_path_score_before: 60,
        top_attack_path_score_after: 40,
        critical_targets_reachable_before: 1,
        critical_targets_reachable_after: 0,
        blast_radius_reachable_before: 8,
        blast_radius_reachable_after: 6,
        blast_radius_critical_before: 1,
        blast_radius_critical_after: 0,
        security_gain: 34.5,
      },
      utility_score: {
        security_gain: 34.5,
        critical_asset_protection: 20,
        blast_radius_reduction: 4,
        evidence_quality: 12.4,
        reversibility_bonus: 10,
        operational_impact_penalty: 10,
        total: 65.5,
      },
      policy_pass: true,
      policy_failed_ids: [],
      recommended: true,
      changed_node_ids: [],
      changed_edge_ids: ['application-pod-01--cloud-database-01'],
      synthetic: true,
    },
  ],
  decision_confidence: {
    anomaly_evidence: 6.25,
    incident_coherence: 4,
    technique_diversity: 3,
    attack_path_corroboration: 0,
    response_simulation_improvement: 20,
    total: 33.25,
    note: 'This is a deterministic evidence-quality score, not a calibrated probability.',
    synthetic: true,
  },
  synthetic: true,
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
      warnings: [],
      synthetic: true,
      created_at: '2026-07-22T00:00:00Z',
      simulation: null,
    },
  ],
}

beforeEach(() => {
  vi.mocked(simulationApi.getSimulationRuns).mockResolvedValue([run])
  vi.mocked(detectionApi.getDetectionModels).mockResolvedValue([model])
  vi.mocked(correlationApi.getRunIncidents).mockResolvedValue(incidents)
  vi.mocked(bluePlanningApi.compareResponsePlans).mockResolvedValue(comparison)
  vi.mocked(responseApi.analyzeResponses).mockResolvedValue(analysis)
})

describe('Blue Agent response plan comparison', () => {
  it('ranks candidate plans and shows the Response Utility Score, not just Defense Score', async () => {
    render(
      <MemoryRouter>
        <ResponsePlansPage />
      </MemoryRouter>,
    )
    await userEvent.selectOptions(await screen.findByLabelText('Blue Agent run'), 'run-1')
    await userEvent.selectOptions(screen.getByLabelText('Blue Agent model'), 'model-1')
    await userEvent.selectOptions(
      await screen.findByLabelText('Blue Agent incident candidate'),
      'candidate-1',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Compare Candidate Plans' }))
    await waitFor(() => {
      expect(bluePlanningApi.compareResponsePlans).toHaveBeenCalled()
    })
    expect(await screen.findByText('Block the network route')).toBeInTheDocument()
    expect(screen.getByText('Recommended plan')).toBeInTheDocument()
    expect(screen.getAllByText(/Response Utility Score/).length).toBeGreaterThan(0)
    expect(screen.getByText(/not a calibrated probability/)).toBeInTheDocument()
  })

  it('surfaces plan-comparison failures without crashing', async () => {
    vi.mocked(bluePlanningApi.compareResponsePlans).mockRejectedValue(
      new Error('Malformed synthetic plan comparison.'),
    )
    render(
      <MemoryRouter>
        <ResponsePlansPage />
      </MemoryRouter>,
    )
    await userEvent.selectOptions(await screen.findByLabelText('Blue Agent run'), 'run-1')
    await userEvent.selectOptions(screen.getByLabelText('Blue Agent model'), 'model-1')
    await userEvent.selectOptions(
      await screen.findByLabelText('Blue Agent incident candidate'),
      'candidate-1',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Compare Candidate Plans' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Malformed synthetic plan comparison.',
    )
  })
})
