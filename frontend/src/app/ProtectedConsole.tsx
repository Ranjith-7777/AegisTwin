import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { DashboardLayout } from '../components/layout/DashboardLayout'
import { isConsoleSession } from '../lib/auth'
import { getSession } from '../services/sessionApi'
import type { SessionView } from '../types/session'
import { AutonomyWorkflowProvider } from './AutonomyWorkflowProvider'
import { SystemDataProvider } from './providers'
import { SimulationPlaybackProvider } from './SimulationPlaybackProvider'

export function ProtectedConsole() {
  const location = useLocation()
  const [session, setSession] = useState<SessionView | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    void getSession()
      .then((value) => {
        if (active) setSession(value)
      })
      .catch(() => {
        if (active) setSession(null)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  if (loading) {
    return (
      <div className="auth-check" role="status">
        <span className="spinner" /> Verifying secure session…
      </div>
    )
  }
  if (!session || !isConsoleSession(session)) {
    const next = `${location.pathname}${location.search}`
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }
  return (
    <SystemDataProvider>
      <SimulationPlaybackProvider>
        <AutonomyWorkflowProvider>
          <DashboardLayout />
        </AutonomyWorkflowProvider>
      </SimulationPlaybackProvider>
    </SystemDataProvider>
  )
}
