import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ExperimentListPage } from '../pages/evaluation/ExperimentListPage'
import * as evaluationApi from '../services/evaluationApi'
import type { ExperimentMetrics, ExperimentView } from '../types/evaluation'

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
    scenario_id: 'scenario-b',
    scenario_name: 'Scenario B',
    seed: 7,
    defence_mode: 'rule_based',
    detection_model_id: 'model-1',
    topology_version: 'v1',
    red_scenario_version: 'v1',
    autonomy_mode: 'observe',
    configuration_json: {},
    started_at: '2026-07-22T00:00:00Z',
    ended_at: null,
    run_id: 'run-2',
    incident_candidate_id: null,
    orchestration_id: null,
    status: 'failed',
    failure_stage: 'running_attack',
    failure_code: 'SYNTHETIC_FAILURE',
    failure_message: 'boom',
    verification_status: null,
    batch_id: null,
    rerun_of_experiment_id: null,
    synthetic: true,
    created_at: '2026-07-22T02:00:00Z',
  },
]

const metrics1: ExperimentMetrics = {
  metrics_version: 'v1',
  logical_timeline: {},
  computation_latency: {},
  raw_metrics: { rollback_required: false },
  normalized_metrics: {},
  computed_at: '2026-07-22T00:05:00Z',
  mci: 0.75,
  mci_version: 'v1',
  ars_total: 70.2,
  ars_pillars: null,
  ars_version: 'v1',
}

beforeEach(() => {
  vi.mocked(evaluationApi.listExperiments).mockResolvedValue(experiments)
  vi.mocked(evaluationApi.getExperimentMetrics).mockResolvedValue(metrics1)
  vi.mocked(evaluationApi.exportExperimentsCsvUrl).mockImplementation((filters = {}) => {
    const params = new URLSearchParams(filters as Record<string, string>)
    const query = params.toString()
    return `/api/v1/evaluation/experiments/export.csv${query ? `?${query}` : ''}`
  })
  vi.mocked(evaluationApi.exportExperimentsJsonUrl).mockImplementation((filters = {}) => {
    const params = new URLSearchParams(filters as Record<string, string>)
    const query = params.toString()
    return `/api/v1/evaluation/experiments/export.json${query ? `?${query}` : ''}`
  })
})

describe('Experiment List', () => {
  it('renders every experiment row with a clear defence-mode label and N/A for missing scores', async () => {
    render(
      <MemoryRouter>
        <ExperimentListPage />
      </MemoryRouter>,
    )
    expect(await screen.findByText('Scenario A')).toBeInTheDocument()
    expect(screen.getByText('Scenario B')).toBeInTheDocument()
    const table = screen.getByRole('table')
    expect(within(table).getByText('AGENTIC')).toBeInTheDocument()
    expect(within(table).getByText('RULE-BASED')).toBeInTheDocument()
    // exp-2 is not completed, so metrics were never fetched for it -> N/A columns.
    const naCells = screen.getAllByText('N/A')
    expect(naCells.length).toBeGreaterThan(0)
  })

  it('re-queries the API when the scenario filter changes', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <ExperimentListPage />
      </MemoryRouter>,
    )
    await screen.findByText('Scenario A')
    await user.type(screen.getByLabelText('Scenario filter'), 'scenario-a')
    await waitFor(() => {
      expect(evaluationApi.listExperiments).toHaveBeenCalledWith(
        expect.objectContaining({ scenario_id: 'scenario-a' }),
      )
    })
  })

  it('renders CSV/JSON export links whose href respects the current filters', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <ExperimentListPage />
      </MemoryRouter>,
    )
    await screen.findByText('Scenario A')
    await user.type(screen.getByLabelText('Scenario filter'), 'scenario-a')
    await waitFor(() => {
      expect(evaluationApi.listExperiments).toHaveBeenCalledWith(
        expect.objectContaining({ scenario_id: 'scenario-a' }),
      )
    })
    const csvLink = screen.getByRole('link', { name: 'Export CSV' })
    const jsonLink = screen.getByRole('link', { name: 'Export JSON' })
    expect(csvLink).toHaveAttribute('href', expect.stringContaining('/experiments/export.csv'))
    expect(csvLink).toHaveAttribute('href', expect.stringContaining('scenario_id=scenario-a'))
    expect(jsonLink).toHaveAttribute('href', expect.stringContaining('/experiments/export.json'))
    expect(csvLink).toHaveAttribute('download')
    expect(jsonLink).toHaveAttribute('download')
  })
})
