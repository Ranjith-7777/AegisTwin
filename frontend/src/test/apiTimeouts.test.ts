import { describe, expect, it } from 'vitest'

import { API_TIMEOUT_MS, COMPUTE_TIMEOUT_MS, LONG_COMPUTE_TIMEOUT_MS } from '../lib/constants'
import { timeoutFor } from '../services/apiClient'

describe('request timeout policy', () => {
  it('keeps quick reads on the default budget', () => {
    expect(timeoutFor('get', '/api/health')).toBe(API_TIMEOUT_MS)
    expect(timeoutFor('get', '/api/v1/simulation/runs')).toBe(API_TIMEOUT_MS)
    expect(timeoutFor('get', '/api/v1/evaluation/experiments')).toBe(API_TIMEOUT_MS)
  })

  it('gives per-run analysis a compute budget', () => {
    expect(timeoutFor('post', '/api/v1/detection/runs/r1/score')).toBe(COMPUTE_TIMEOUT_MS)
    expect(timeoutFor('post', '/api/v1/correlation/runs/r1/analyze')).toBe(COMPUTE_TIMEOUT_MS)
    expect(timeoutFor('post', '/api/v1/response/runs/r1/analyze')).toBe(COMPUTE_TIMEOUT_MS)
    expect(timeoutFor('post', '/api/v1/orchestration/o1/verify')).toBe(COMPUTE_TIMEOUT_MS)
    expect(timeoutFor('get', '/api/v1/evaluation/compare?seed=84')).toBe(COMPUTE_TIMEOUT_MS)
  })

  it('gives training, purple team, evaluation and the autonomous loop a long budget', () => {
    expect(timeoutFor('post', '/api/v1/detection/models/train')).toBe(LONG_COMPUTE_TIMEOUT_MS)
    expect(timeoutFor('post', '/api/v1/purple-team/experiments')).toBe(LONG_COMPUTE_TIMEOUT_MS)
    expect(timeoutFor('post', '/api/v1/evaluation/batches')).toBe(LONG_COMPUTE_TIMEOUT_MS)
    expect(timeoutFor('post', '/api/v1/evaluation/experiments/e1/rerun')).toBe(
      LONG_COMPUTE_TIMEOUT_MS,
    )
    expect(timeoutFor('post', '/api/v1/workflow/runs/r1/execute')).toBe(LONG_COMPUTE_TIMEOUT_MS)
  })

  it('never makes a request unlimited', () => {
    const paths = ['/api/v1/detection/models/train', '/api/v1/topology', '/anything']
    for (const path of paths) {
      expect(timeoutFor('post', path)).toBeGreaterThan(0)
      expect(timeoutFor('post', path)).toBeLessThanOrEqual(LONG_COMPUTE_TIMEOUT_MS)
    }
  })
})
