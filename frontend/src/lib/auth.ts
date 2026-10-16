import type { SessionView } from '../types/session'

/**
 * Development access is asserted by the backend, never selected by the
 * browser. The production check is deliberately duplicated here so an
 * impossible/malformed production development session fails closed in the UI
 * as well as in backend configuration and startup validation.
 */
export function isDevelopmentSession(session: SessionView): boolean {
  return (
    session.authenticated &&
    session.auth_mode === 'development_bypass' &&
    session.environment !== 'production'
  )
}

export function isConsoleSession(session: SessionView): boolean {
  return (
    (session.authenticated && session.auth_mode === 'easy_auth') || isDevelopmentSession(session)
  )
}
