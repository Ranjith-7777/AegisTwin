export const FALLBACK_SAFETY_MESSAGE =
  'AegisTwin uses synthetic telemetry and simulated infrastructure. No action affects real systems.'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
export const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL ?? 'ws://localhost:8000'
export const API_TIMEOUT_MS = 5_000
