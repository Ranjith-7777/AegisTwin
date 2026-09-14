import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ExperimentDetailPage } from '../pages/evaluation/ExperimentDetailPage'
import * as evaluationApi from '../services/evaluationApi'
import type { ExperimentDetail } from '../types/evaluation'

vi.mock('../services/evaluationApi')

const baseExperiment: ExperimentDetail = {
  experiment_id: 'exp-1',
  scenario_id: 'scenario-a',
  scenario_name: 'Scenario A',
  seed: 1,
  defence_mode: 'agentic',
  detection_model_id: 'model-1',
  topology_version: 'topo-v1',
  red_scenario_version: 'red-v1',
  autonomy_mode: 'autonomous',
  configuration_json: {},
  started_at: '2026-07-22T00:00:00Z',
  ended_at: '2026-07-22T00:05:00Z',
  run_id: 'run-1',
  incident_candidate_id: 'candidate-1',
  orchestration_id: 'orch-1',
  status: 'completed',
  failure_stage: null,
  failure_code: null,
  failure_message: null,
  verification_status: 'successful_simulation',
  batch_id: null,
  rerun_of_experiment_id: null,
  synthetic: true,
  created_at: '2026-07-22T00:00:00Z',
  metrics: {
    metrics_version: 'metrics-v1',
    logical_timeline: {},
    computation_latency: {},
    raw_metrics: { detection_coverage: 0, attack_path_reduction: 3 },
    normalized_metrics: {
      detection_timeliness: { value: 0.5, applicable: true },
      operational_disruption: { value: null, applicable: false, note: 'no telemetry available' },
    },
    computed_at: '2026-07-22T00:05:00Z',
    mci: 0.913,
    mci_version: 'mci-v1',
    ars_total: 82.4,
    ars_pillars: {
      A: { value: 0.9, applicable: true },
      W: { value: null, applicable: false, note: 'not applicable for this mode' },
      M: { value: 0.755, applicable: true },
      R: { value: 0.88, applicable: true },
      effective_pillar_weights: { A: 0.2, W: 0.35, M: 0.25, R: 0.2 },
    },
    ars_version: 'ars-v1',
  },
  mission_health_curve: [
    { sequence: 1, logical_time_sim: 0, mission_health: 1, stage: 'baseline', reason: 'start' },
    { sequence: 2, logical_time_sim: 30, mission_health: 0.4, stage: 'attack', reason: 'impact' },
  ],
  timeline: {
    experiment_id: 'exp-1',
    events: [
      {
        sequence: 1,
        stage: 'detection',
        logical_time_sim: 5,
        wall_clock_time: '2026-07-22T00:01:00Z',
        status: 'occurred',
        summary: 'Detected the synthetic anomaly.',
        resource_ids: [],
        correlation_id: null,
        causation_id: null,
      },
      {
        sequence: 2,
        stage: 'rollback',
        logical_time_sim: null,
        wall_clock_time: null,
        status: 'skipped_not_applicable',
        summary: 'Rollback was never required.',
        resource_ids: [],
        correlation_id: null,
        causation_id: null,
      },
    ],
    synthetic: true,
  },
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/evaluation/experiments/exp-1']}>
      <Routes>
        <Route path="/evaluation/experiments/:experimentId" element={<ExperimentDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Experiment Detail', () => {
  beforeEach(() => {
    vi.mocked(evaluationApi.getExperiment).mockReset()
    vi.mocked(evaluationApi.rerunExperiment).mockReset()
  })

  it('shows a loading state before the experiment resolves', () => {
    vi.mocked(evaluationApi.getExperiment).mockReturnValue(new Promise(() => undefined))
    renderPage()
    expect(screen.getByRole('status')).toHaveTextContent('Loading experiment…')
  })

  it('renders ARS, MCI, metrics (with N/A distinct from real zero) and the timeline', async () => {
    vi.mocked(evaluationApi.getExperiment).mockResolvedValue(baseExperiment)
    renderPage()

    expect(await screen.findByText('82.4 / 100')).toBeInTheDocument()
    expect(
      screen.getByText('Deterministic evaluation score, not a probability.'),
    ).toBeInTheDocument()
    expect(screen.getByText('0.913')).toBeInTheDocument()

    // A real zero raw metric renders as "0", never as N/A.
    expect(screen.getByText('0')).toBeInTheDocument()
    // An inapplicable normalized metric renders as N/A, not blank/0.
    expect(screen.getAllByText('N/A').length).toBeGreaterThan(0)

    expect(screen.getByText('Detected the synthetic anomaly.')).toBeInTheDocument()
    expect(screen.getByText('Rollback was never required.')).toBeInTheDocument()
    expect(screen.getByText('skipped — not applicable')).toBeInTheDocument()
  })

  it('shows the CONTROL badge and explanatory copy for no_active_defence, not a failure state', async () => {
    vi.mocked(evaluationApi.getExperiment).mockResolvedValue({
      ...baseExperiment,
      defence_mode: 'no_active_defence',
    })
    renderPage()
    expect(await screen.findByText('CONTROL — NO ACTIVE DEFENCE')).toBeInTheDocument()
    expect(
      screen.getByText(/Attack observed for evaluation; no mitigation is applied\./),
    ).toBeInTheDocument()
  })

  it('shows a clear error state on a 404', async () => {
    vi.mocked(evaluationApi.getExperiment).mockRejectedValue(new Error('not found'))
    renderPage()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('re-runs the experiment and navigates to the new experiment on success', async () => {
    const user = userEvent.setup()
    vi.mocked(evaluationApi.getExperiment).mockResolvedValue(baseExperiment)
    vi.mocked(evaluationApi.rerunExperiment).mockResolvedValue({
      ...baseExperiment,
      experiment_id: 'exp-2',
    })
    renderPage()
    await screen.findByText('82.4 / 100')
    await user.click(screen.getByRole('button', { name: /Re-run experiment/i }))
    await waitFor(() => {
      expect(evaluationApi.rerunExperiment).toHaveBeenCalledWith('exp-1')
    })
  })
})
