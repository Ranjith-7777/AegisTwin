import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { EvaluationOverviewPage } from '../pages/evaluation/EvaluationOverviewPage'
import * as evaluationApi from '../services/evaluationApi'
import type { BatchView, ExperimentMetrics, ExperimentView } from '../types/evaluation'

vi.mock('../services/evaluationApi')

const experiments: ExperimentView[] = [
  {
    experiment_id: 'exp-1',
    scenario_id: 'scenario-a',
    scenario_name: 'Scenario A',
    seed: 1,
    defence_mode: 'agentic',
    detection_model_id: 'model-1',
    topology_version: 'v1',
    red_scenario_version: 'v1',
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
  },
  {
    experiment_id: 'exp-2',
    scenario_id: 'scenario-a',
    scenario_name: 'Scenario A',
    seed: 2,
    defence_mode: 'no_active_defence',
    detection_model_id: null,
    topology_version: 'v1',
    red_scenario_version: 'v1',
    autonomy_mode: null,
    configuration_json: {},
    started_at: '2026-07-22T00:00:00Z',
    ended_at: '2026-07-22T00:05:00Z',
    run_id: 'run-2',
    incident_candidate_id: null,
    orchestration_id: null,
    status: 'completed',
    failure_stage: null,
    failure_code: null,
    failure_message: null,
    verification_status: null,
    batch_id: null,
    rerun_of_experiment_id: null,
    synthetic: true,
    created_at: '2026-07-22T01:00:00Z',
  },
]

const metrics1: ExperimentMetrics = {
  metrics_version: 'v1',
  logical_timeline: {},
  computation_latency: {},
  raw_metrics: {},
  normalized_metrics: {},
  computed_at: '2026-07-22T00:05:00Z',
  mci: 0.82,
  mci_version: 'v1',
  ars_total: 82.4,
  ars_pillars: null,
  ars_version: 'v1',
}

const batches: BatchView[] = [
  {
    batch_id: 'batch-1',
    scenario_ids: ['scenario-a'],
    seeds: [1, 2],
    defence_modes: ['agentic', 'no_active_defence'],
    status: 'completed',
    total_experiments: 2,
    completed_count: 2,
    failed_count: 0,
    experiment_ids: ['exp-1', 'exp-2'],
    max_experiments: null,
    truncated: false,
    started_at: '2026-07-22T00:00:00Z',
    ended_at: '2026-07-22T00:10:00Z',
    runtime_seconds: 600,
    created_at: '2026-07-22T00:10:00Z',
    synthetic: true,
  },
]

beforeEach(() => {
  vi.mocked(evaluationApi.listExperiments).mockResolvedValue(experiments)
  vi.mocked(evaluationApi.listBatches).mockResolvedValue(batches)
  vi.mocked(evaluationApi.getExperimentMetrics).mockImplementation((id: string) =>
    Promise.resolve(id === 'exp-1' ? metrics1 : null),
  )
})

describe('Evaluation Overview', () => {
  it('renders real aggregate numbers derived from the mocked API responses', async () => {
    render(
      <MemoryRouter>
        <EvaluationOverviewPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('2')).toBeInTheDocument() // total experiments
    expect(screen.getByText('NO ACTIVE DEFENCE')).toBeInTheDocument()
    expect(screen.getByText('AGENTIC')).toBeInTheDocument()
    expect(await screen.findByText('82.4 / 100')).toBeInTheDocument()
    expect(screen.getByText('0.820')).toBeInTheDocument()
    expect(screen.getByText(/Batch batch-1: 2\/2 completed/)).toBeInTheDocument()
  })
})
