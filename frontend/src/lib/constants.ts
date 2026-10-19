export const APP_NAME = 'AegisArena'
export const APP_TAGLINE = 'Autonomous Cloud Cyber-Resilience Digital Twin'
export const APP_FULL_NAME = `${APP_NAME} — ${APP_TAGLINE}`
export const FALLBACK_SAFETY_MESSAGE =
  'AegisArena uses synthetic telemetry and a simulated cloud estate. No action affects real systems.'

const sameOrigin = typeof window === 'undefined' ? '' : window.location.origin
const sameHostSocket =
  typeof window === 'undefined'
    ? ''
    : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`

// Empty or unset means same-origin (nginx in Docker/Azure proxies /api and /ws).
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || sameOrigin
export const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || sameHostSocket
export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'
export const DEPLOYMENT_ENV = import.meta.env.VITE_DEPLOYMENT_ENV ?? 'development'
/** Default for reads and quick writes. */
export const API_TIMEOUT_MS = 15_000
/** Per-run analysis (scoring, correlation, prediction, Blue ranking, orchestration steps). */
export const COMPUTE_TIMEOUT_MS = 60_000
/** Model training, purple-team runs, evaluation experiments/batches, the autonomous loop. */
export const LONG_COMPUTE_TIMEOUT_MS = 300_000
