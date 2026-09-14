import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ComparisonPage } from '../pages/evaluation/ComparisonPage'
import * as evaluationApi from '../services/evaluationApi'
import * as purpleTeamApi from '../services/purpleTeamApi'
import type { ModeComparisonResult } from '../types/evaluation'
import type { RedScenarioSummary } from '../types/purpleTeam'

vi.mock('../services/evaluationApi')
vi.mock('../services/purpleTeamApi')

const scenarios: RedScenarioSummary[] = [
  {
    scenario_id: 'ddos-traffic-spike',
    name: 'DDoS Traffic Spike',
    description: 'desc',
    is_red_agent_scenario: false,
    step_count: 3,
    mitre_technique_ids: [],
    step_techniques: [],
    synthetic: true,
  },
]

const comparisonWithNa: ModeComparisonResult = {
  scenario_id: 'ddos-traffic-spike',
  seed: 17,
  baseline_mode: 'no_active_defence',
  available_modes: ['no_active_defence', 'rule_based', 'agentic'],
  missing_modes: ['ml_assisted'],
  rows: [
    {
      metric: 'ars_total',
      values: {
        no_active_defence: { value: 10, applicable: true },
        rule_based: { value: 40, applicable: true },
        agentic: { value: 55, applicable: true },
      },
    },
    {
      metric: 'attack_path_reduction',
      values: {
        no_active_defence: { value: null, applicable: false },
        rule_based: { value: 0.3, applicable: true },
        agentic: { value: 0.6, applicable: true },
      },
    },
  ],
  paired_deltas: [
    {
      metric: 'ars_total',
      reference_mode: 'rule_based',
      compared_mode: 'agentic',
      reference_value: 40,
      compared_value: 55,
      delta: 15,
      paired: true,
      fairness_reasons: [],
    },
    {
      metric: 'ars_total',
      reference_mode: 'no_active_defence',
      compared_mode: 'ml_assisted',
      reference_value: 10,
      compared_value: 20,
      delta: 10,
      paired: false,
      fairness_reasons: ['different seeds observed'],
    },
  ],
  synthetic: true,
}

beforeEach(() => {
  vi.mocked(purpleTeamApi.listRedScenarios).mockResolvedValue(scenarios)
  vi.mocked(evaluationApi.compareModes).mockResolvedValue(comparisonWithNa)
})

describe('Comparison dashboard', () => {
  it('renders the comparison table with N/A and missing-mode handling, and an unpaired-delta warning', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <ComparisonPage />
      </MemoryRouter>,
    )
    await screen.findByText('DDoS Traffic Spike')
    await user.click(screen.getByRole('button', { name: /compare modes/i }))

    await waitFor(() => {
      expect(evaluationApi.compareModes).toHaveBeenCalledWith(
        expect.objectContaining({ scenarioId: 'ddos-traffic-spike' }),
      )
    })

    const table = await screen.findByRole('table')
    expect(within(table).getByText('N/A')).toBeInTheDocument()
    expect(screen.getByText(/No experiment found for/)).toBeInTheDocument()

    // Paired delta warning for the unpaired ml_assisted comparison.
    expect(screen.getByText('unpaired')).toBeInTheDocument()
    expect(screen.getByText(/not a fair paired comparison/i)).toBeInTheDocument()
    expect(screen.getByText('fairness-confirmed')).toBeInTheDocument()
  })

  it('shows an error state when the API call fails', async () => {
    vi.mocked(evaluationApi.compareModes).mockRejectedValue(new Error('boom'))
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <ComparisonPage />
      </MemoryRouter>,
    )
    await screen.findByText('DDoS Traffic Spike')
    await user.click(screen.getByRole('button', { name: /compare modes/i }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
