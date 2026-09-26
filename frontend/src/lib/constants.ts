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

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? sameOrigin
export const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL ?? sameHostSocket
export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'
export const DEPLOYMENT_ENV = import.meta.env.VITE_DEPLOYMENT_ENV ?? 'development'
export const API_TIMEOUT_MS = 5_000
