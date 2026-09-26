import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ExperimentReportPage } from '../pages/evaluation/ExperimentReportPage'
import * as evaluationApi from '../services/evaluationApi'
import type { ExperimentReport } from '../types/evaluation'

vi.mock('../services/evaluationApi')

const report: ExperimentReport = {
  experiment_id: 'exp-1',
  executive_summary: "Experiment exp-1 ran 'Scenario A' (seed=17) under 'agentic' defence.",
  configuration: { top_k: 5 },
  attack_techniques_observed: ['T1078'],
  detection_evidence_summary: { detection_coverage: 0.8 },
  incident_summary: { priority: 'high' },
  attack_graph_and_blast_radius: { attack_path_reduction: 0.5 },
  response_verification_rollback_summary: { containment_success: true },
  metrics: {
    metrics_version: 'v1',
    logical_timeline: {},
    computation_latency: {},
    raw_metrics: { detection_coverage: 0.8 },
    normalized_metrics: {
      detection_coverage: { value: 0.8, applicable: true },
    },
    computed_at: '2026-07-22T00:05:00Z',
    mci: 0.75,
    mci_version: 'v1',
    ars_total: 62.3,
    ars_pillars: null,
    ars_version: 'v1',
  },
  mission_continuity_index: 0.75,
  ars_decomposition: { anticipate: 12.5 },
  paired_baseline_comparison: {
    scenario_id: 'scenario-a',
    seed: 17,
    baseline_mode: 'no_active_defence',
    available_modes: ['no_active_defence', 'agentic'],
    missing_modes: [],
    rows: [
      {
        metric: 'ars_total',
        values: {
          no_active_defence: { value: 10, applicable: true },
          agentic: { value: 62.3, applicable: true },
        },
      },
    ],
    paired_deltas: [],
    synthetic: true,
  },
  limitations: ['Sample size of one experiment; no statistical significance implied.'],
  reproduction: { experiment_id: 'exp-1', scenario_id: 'scenario-a', seed: 17 },
  synthetic: true,
}

beforeEach(() => {
  vi.mocked(evaluationApi.getExperimentReport).mockResolvedValue(report)
})

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/evaluation/experiments/exp-1/report']}>
      <Routes>
        <Route
          path="/evaluation/experiments/:experimentId/report"
          element={<ExperimentReportPage />}
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Experiment Report page', () => {
  it('renders every report section as a single-column document', async () => {
    renderPage()
    expect(await screen.findByText('Executive summary')).toBeInTheDocument()
    expect(screen.getByText(report.executive_summary)).toBeInTheDocument()
    expect(screen.getByText('Configuration')).toBeInTheDocument()
    expect(screen.getByText('ATT&CK techniques observed')).toBeInTheDocument()
    expect(screen.getByText('T1078')).toBeInTheDocument()
    expect(screen.getByText('Detection evidence summary')).toBeInTheDocument()
    expect(screen.getByText('Incident summary')).toBeInTheDocument()
    expect(screen.getByText('Attack graph & blast radius')).toBeInTheDocument()
    expect(screen.getByText('Response, verification & rollback summary')).toBeInTheDocument()
    expect(screen.getByText('MOP / MOE metrics')).toBeInTheDocument()
    expect(screen.getByText('Mission Continuity Index')).toBeInTheDocument()
    expect(screen.getByText('0.750')).toBeInTheDocument()
    expect(screen.getByText('Aegis Resilience Score decomposition')).toBeInTheDocument()
    expect(screen.getByText('Paired baseline comparison')).toBeInTheDocument()
    expect(screen.getByText('Limitations')).toBeInTheDocument()
    expect(
      screen.getByText('Sample size of one experiment; no statistical significance implied.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Reproduction metadata')).toBeInTheDocument()
  })

  it('has a print button that calls window.print', async () => {
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => undefined)
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    renderPage()
    const button = await screen.findByRole('button', { name: /print \/ save as pdf/i })
    await user.click(button)
    expect(printSpy).toHaveBeenCalled()
    printSpy.mockRestore()
  })

  it('shows a loading state, then an error state on failure', async () => {
    vi.mocked(evaluationApi.getExperimentReport).mockRejectedValue(new Error('boom'))
    renderPage()
    expect(screen.getByText(/Loading report/)).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
