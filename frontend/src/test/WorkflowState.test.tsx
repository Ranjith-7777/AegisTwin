import { AxiosError, AxiosHeaders } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getWorkflowState } from '../services/workflowApi'

// Regression for the identical-replay inconsistency: a reused deterministic
// run must restore the ranked comparison together with its orchestration.
const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('../services/apiClient', () => ({ apiClient: { get, post: vi.fn() } }))

function httpError(status: number) {
  const headers = new AxiosHeaders()
  return new AxiosError('failed', String(status), { headers }, null, {
    status,
    statusText: '',
    headers: {},
    config: { headers },
    data: {},
  })
}

beforeEach(() => {
  get.mockReset()
})

describe('getWorkflowState', () => {
  it('requests the persisted state for the exact run and model', async () => {
    const state = {
      comparison: { candidates: [], through_sequence_number: 12 },
      orchestration: null,
      autonomy_mode: 'recommend',
      auto_executed: false,
      auto_verified: false,
      stopped_reason: 'Restored',
      restored: true,
      synthetic: true,
    }
    get.mockResolvedValue({ data: state })
    await expect(getWorkflowState('run/1', 'model-1')).resolves.toEqual(state)
    expect(get).toHaveBeenCalledWith('/api/v1/workflow/runs/run%2F1/state', {
      params: { model_id: 'model-1' },
    })
  })

  it('returns null when nothing has been recorded for the run', async () => {
    get.mockRejectedValue(httpError(404))
    await expect(getWorkflowState('run-1', 'model-1')).resolves.toBeNull()
  })

  it('propagates other failures instead of hiding them as "no state"', async () => {
    get.mockRejectedValue(httpError(500))
    await expect(getWorkflowState('run-1', 'model-1')).rejects.toBeInstanceOf(AxiosError)
  })

  it('rejects a malformed comparison', async () => {
    get.mockResolvedValue({
      data: { comparison: { candidates: 'nope' }, orchestration: null },
    })
    await expect(getWorkflowState('run-1', 'model-1')).rejects.toThrow(/Malformed/)
  })
})
