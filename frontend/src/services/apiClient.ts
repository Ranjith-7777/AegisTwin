import axios, { AxiosError } from 'axios'

import {
  API_BASE_URL,
  API_TIMEOUT_MS,
  COMPUTE_TIMEOUT_MS,
  LONG_COMPUTE_TIMEOUT_MS,
} from '../lib/constants'
import type { ApiErrorResponse, ClientApiError } from '../types/api'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT_MS,
  headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
})

/**
 * Request-specific timeouts. Most endpoints answer in milliseconds, but some
 * legitimately compute for longer (especially on a 0.25 vCPU cloud replica),
 * so the budget is chosen per endpoint instead of one tiny universal limit.
 * A call that passes its own `timeout` keeps it.
 */
const TIMEOUT_POLICY: { method: string; pattern: RegExp; timeout: number }[] = [
  { method: 'post', pattern: /\/detection\/models\/train$/, timeout: LONG_COMPUTE_TIMEOUT_MS },
  {
    method: 'post',
    pattern: /\/detection\/models\/[^/]+\/evaluate$/,
    timeout: LONG_COMPUTE_TIMEOUT_MS,
  },
  { method: 'post', pattern: /\/purple-team\/experiments$/, timeout: LONG_COMPUTE_TIMEOUT_MS },
  {
    method: 'post',
    pattern: /\/workflow\/runs\/[^/]+\/execute$/,
    timeout: LONG_COMPUTE_TIMEOUT_MS,
  },
  {
    method: 'post',
    pattern: /\/evaluation\/(experiments|batches|robustness)(\/|$)/,
    timeout: LONG_COMPUTE_TIMEOUT_MS,
  },
  { method: 'get', pattern: /\/evaluation\/(compare|aggregate)$/, timeout: COMPUTE_TIMEOUT_MS },
  { method: 'post', pattern: /\/detection\/runs\/[^/]+\/score$/, timeout: COMPUTE_TIMEOUT_MS },
  {
    method: 'post',
    pattern: /\/(correlation|prediction|response)\/runs\/[^/]+\/(analyze|evaluate)$/,
    timeout: COMPUTE_TIMEOUT_MS,
  },
  {
    method: 'post',
    pattern: /\/blue-planning\/runs\/[^/]+\/compare$/,
    timeout: COMPUTE_TIMEOUT_MS,
  },
  { method: 'post', pattern: /\/orchestration\//, timeout: COMPUTE_TIMEOUT_MS },
  { method: 'post', pattern: /\/blast-radius$/, timeout: COMPUTE_TIMEOUT_MS },
  { method: 'get', pattern: /\/attack-graph\/paths$/, timeout: COMPUTE_TIMEOUT_MS },
  { method: 'get', pattern: /\/data-sources\/[^/]+\/findings$/, timeout: LONG_COMPUTE_TIMEOUT_MS },
]

export function timeoutFor(method: string | undefined, url: string | undefined): number {
  const verb = (method ?? 'get').toLowerCase()
  const path = (url ?? '').split('?')[0] ?? ''
  return (
    TIMEOUT_POLICY.find((rule) => rule.method === verb && rule.pattern.test(path))?.timeout ??
    API_TIMEOUT_MS
  )
}

apiClient.interceptors.request.use((config) => {
  if (config.timeout === undefined || config.timeout === API_TIMEOUT_MS) {
    config.timeout = timeoutFor(config.method, config.url)
  }
  return config
})

export function toClientApiError(error: unknown): ClientApiError {
  if (error instanceof AxiosError) {
    const response = error.response?.data as Partial<ApiErrorResponse> | undefined
    const correlationId =
      response?.correlation_id ??
      (typeof error.response?.headers['x-correlation-id'] === 'string'
        ? error.response.headers['x-correlation-id']
        : undefined)
    const timedOut = error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT'
    return {
      message:
        response?.message ??
        (timedOut
          ? 'The AegisArena backend did not respond in time. The operation may still be running.'
          : 'The AegisArena backend is unavailable.'),
      correlationId,
    }
  }
  return { message: 'The AegisArena backend is unavailable.' }
}
