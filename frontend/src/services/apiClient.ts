import axios, { AxiosError } from 'axios'

import { API_BASE_URL, API_TIMEOUT_MS } from '../lib/constants'
import type { ApiErrorResponse, ClientApiError } from '../types/api'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT_MS,
  headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
})

export function toClientApiError(error: unknown): ClientApiError {
  if (error instanceof AxiosError) {
    const response = error.response?.data as Partial<ApiErrorResponse> | undefined
    const correlationId =
      response?.correlation_id ??
      (typeof error.response?.headers['x-correlation-id'] === 'string'
        ? error.response.headers['x-correlation-id']
        : undefined)
    return {
      message: response?.message ?? 'The AegisTwin backend is unavailable.',
      correlationId,
    }
  }
  return { message: 'The AegisTwin backend is unavailable.' }
}
