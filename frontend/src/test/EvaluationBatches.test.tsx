import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { BatchesPage } from '../pages/evaluation/BatchesPage'
import * as evaluationApi from '../services/evaluationApi'
import * as purpleTeamApi from '../services/purpleTeamApi'
import type { BatchView } from '../types/evaluation'

vi.mock('../services/evaluationApi')
vi.mock('../services/purpleTeamApi')

const completedBatch: BatchView = {
  batch_id: 'batch-1234567890',
  scenario_ids: ['ddos-traffic-spike'],
  seeds: [17],
  defence_modes: ['agentic'],
  status: 'completed',
  total_experiments: 1,
  completed_count: 1,
  failed_count: 0,
  experiment_ids: ['exp-1'],
  max_experiments: null,
  truncated: false,
  started_at: '2026-07-22T00:00:00Z',
  ended_at: '2026-07-22T00:01:00Z',
  runtime_seconds: 12.5,
  created_at: '2026-07-22T00:00:00Z',
  synthetic: true,
}

const withFailuresBatch: BatchView = {
  ...completedBatch,
  batch_id: 'batch-failures',
  status: 'completed_with_failures',
  completed_count: 3,
  failed_count: 1,
  total_experiments: 4,
  experiment_ids: ['exp-1', 'exp-2', 'exp-3'],
}

beforeEach(() => {
  vi.mocked(purpleTeamApi.listRedScenarios).mockResolvedValue([])
  vi.mocked(evaluationApi.listBatches).mockResolvedValue([completedBatch])
  vi.mocked(evaluationApi.getBatch).mockResolvedValue(completedBatch)
  vi.mocked(evaluationApi.createBatch).mockResolvedValue(completedBatch)
})

describe('Batches page', () => {
  it('lists past batches, loading and empty states', async () => {
    vi.mocked(evaluationApi.listBatches).mockResolvedValue([])
    render(
      <MemoryRouter>
        <BatchesPage />
      </MemoryRouter>,
    )
    expect(screen.getByText(/Loading batches/)).toBeInTheDocument()
    expect(await screen.findByText(/No batches have been run yet/)).toBeInTheDocument()
  })

  it('creates a batch, shows the elapsed-time loading state, then renders the completed batch', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    let resolveCreateBatch: (batch: BatchView) => void = () => {
      throw new Error('resolveCreateBatch called before it was assigned')
    }
    vi.mocked(evaluationApi.createBatch).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCreateBatch = resolve
        }),
    )
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <BatchesPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(screen.getAllByRole('button').some((el) => el.textContent.includes('batch-12'))).toBe(
        true,
      )
    })

    // Only the scenario checkboxes start unchecked; seeds and defence modes
    // default to the full canonical set already checked.
    await user.click(screen.getByLabelText('Scenario ddos-traffic-spike'))
    await user.click(screen.getByRole('button', { name: /^run batch$/i }))

    expect(await screen.findByText(/Running batch/)).toBeInTheDocument()

    expect(evaluationApi.createBatch).toHaveBeenCalledWith(
      expect.objectContaining({
        scenario_ids: ['ddos-traffic-spike'],
      }),
    )

    resolveCreateBatch(completedBatch)

    expect(await screen.findByText('Batch complete')).toBeInTheDocument()
    expect(screen.getAllByText(/1 \/ 1/).length).toBeGreaterThan(0)
  })

  it('renders a completed_with_failures batch non-alarmingly', async () => {
    vi.mocked(evaluationApi.listBatches).mockResolvedValue([withFailuresBatch])
    vi.mocked(evaluationApi.getBatch).mockResolvedValue(withFailuresBatch)
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <BatchesPage />
      </MemoryRouter>,
    )
    let batchButton: HTMLElement | undefined
    await waitFor(() => {
      batchButton = screen.getAllByRole('button').find((el) => el.textContent.includes('batch-fa'))
      expect(batchButton).toBeDefined()
    })
    await user.click(batchButton as HTMLElement)
    expect(await screen.findByText('Batch summary')).toBeInTheDocument()
    expect(
      screen.getByText(/failed. This does not indicate the batch itself is broken/),
    ).toBeInTheDocument()
  })

  it('shows an error state when the batch list fails to load', async () => {
    vi.mocked(evaluationApi.listBatches).mockRejectedValue(new Error('boom'))
    render(
      <MemoryRouter>
        <BatchesPage />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
