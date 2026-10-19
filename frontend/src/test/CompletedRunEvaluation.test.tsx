import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CompletedRunEvaluation } from '../components/workflow/CompletedRunEvaluation'
import * as evaluationApi from '../services/evaluationApi'
import type { ExperimentDetail } from '../types/evaluation'

vi.mock('../services/evaluationApi')

describe('CompletedRunEvaluation', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('evaluates terminal evidence and navigates directly to its report', async () => {
    vi.mocked(evaluationApi.evaluateCompletedWorkflow).mockResolvedValue({
      experiment_id: 'workflow-evaluation-1',
    } as ExperimentDetail)
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/workflow']}>
        <Routes>
          <Route
            path="/workflow"
            element={
              <CompletedRunEvaluation
                orchestrationId="orchestration-1"
                state="verified"
                canOperate
              />
            }
          />
          <Route
            path="/evaluation/experiments/:experimentId/report"
            element={<h1>Traceable evaluation report</h1>}
          />
        </Routes>
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { name: 'Evaluate completed run' }))

    expect(evaluationApi.evaluateCompletedWorkflow).toHaveBeenCalledWith('orchestration-1')
    expect(
      await screen.findByRole('heading', { name: 'Traceable evaluation report' }),
    ).toBeVisible()
  })

  it('does not offer evaluation for an incomplete workflow', () => {
    render(
      <MemoryRouter>
        <CompletedRunEvaluation
          orchestrationId="orchestration-1"
          state="awaiting_analyst_approval"
          canOperate
        />
      </MemoryRouter>,
    )

    expect(screen.queryByRole('button', { name: 'Evaluate completed run' })).toBeNull()
  })
})
