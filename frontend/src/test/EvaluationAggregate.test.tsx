import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AggregatePage } from '../pages/evaluation/AggregatePage'
import * as evaluationApi from '../services/evaluationApi'
import * as purpleTeamApi from '../services/purpleTeamApi'
import type { AggregateResultView } from '../types/evaluation'

vi.mock('../services/evaluationApi')
vi.mock('../services/purpleTeamApi')

const aggregateResult: AggregateResultView = {
  group_label: 'scenario=ddos-traffic-spike',
  experiment_count: 5,
  metric_summaries: {
    ars_total: {
      count: 5,
      n_applicable: 5,
      mean: 42.5,
      median: 43,
      std: 3.2,
      minimum: 38,
      maximum: 47,
    },
    attack_path_reduction: {
      count: 5,
      n_applicable: 2,
      mean: 0.4,
      median: 0.4,
      std: 0.05,
      minimum: 0.35,
      maximum: 0.45,
    },
  },
  boolean_summaries: {
    verification_success: {
      total_applicable: 4,
      success_count: 3,
      success_rate: 0.75,
    },
  },
}

beforeEach(() => {
  vi.mocked(purpleTeamApi.listRedScenarios).mockResolvedValue([])
  vi.mocked(evaluationApi.aggregate).mockResolvedValue(aggregateResult)
})

describe('Aggregate view', () => {
  it('renders a labeled scope, mean ± std, and flags small samples without significance claims', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <AggregatePage />
      </MemoryRouter>,
    )
    await user.click(screen.getByRole('button', { name: /^aggregate$/i }))

    await waitFor(() => {
      expect(evaluationApi.aggregate).toHaveBeenCalled()
    })

    expect(await screen.findByText(/Aggregated across 5 completed experiment/)).toBeInTheDocument()
    expect(screen.getByText('42.500 ± 3.200')).toBeInTheDocument()
    expect(screen.getAllByText('small sample').length).toBeGreaterThan(0)
    expect(screen.getByText('75%')).toBeInTheDocument()
    // The page explicitly disclaims p-values/significance in its intro copy,
    // but must never render an actual computed p-value or significance flag.
    expect(screen.queryByText(/p\s*=\s*0/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/statistically significant/i)).not.toBeInTheDocument()
  })

  it('shows an empty state when no completed experiments match', async () => {
    vi.mocked(evaluationApi.aggregate).mockResolvedValue({
      group_label: 'none',
      experiment_count: 0,
      metric_summaries: {},
      boolean_summaries: {},
    })
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <AggregatePage />
      </MemoryRouter>,
    )
    await user.click(screen.getByRole('button', { name: /^aggregate$/i }))
    expect(await screen.findByText(/No completed experiments match/)).toBeInTheDocument()
  })

  it('shows an error state when the API call fails', async () => {
    vi.mocked(evaluationApi.aggregate).mockRejectedValue(new Error('boom'))
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <AggregatePage />
      </MemoryRouter>,
    )
    await user.click(screen.getByRole('button', { name: /^aggregate$/i }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
