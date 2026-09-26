import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { toClientApiError } from '../services/apiClient'
import { getHealth, getSafetyStatus, getSystemStatus } from '../services/systemApi'
import type {
  ClientApiError,
  HealthResponse,
  SafetyResponse,
  SystemStatusResponse,
} from '../types/api'
import { SystemDataContext } from './systemDataContext'

export function SystemDataProvider({ children }: { children: ReactNode }) {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [system, setSystem] = useState<SystemStatusResponse | null>(null)
  const [safety, setSafety] = useState<SafetyResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ClientApiError | null>(null)
  const [requestVersion, setRequestVersion] = useState(0)

  const refresh = useCallback(() => {
    setLoading(true)
    setError(null)
    setRequestVersion((version) => version + 1)
  }, [])

  useEffect(() => {
    let active = true
    void Promise.allSettled([getHealth(), getSystemStatus(), getSafetyStatus()]).then((results) => {
      if (!active) return
      const [healthResult, systemResult, safetyResult] = results
      setHealth(healthResult.status === 'fulfilled' ? healthResult.value : null)
      setSystem(systemResult.status === 'fulfilled' ? systemResult.value : null)
      setSafety(safetyResult.status === 'fulfilled' ? safetyResult.value : null)
      const failure = results.find((result) => result.status === 'rejected')
      if (failure?.status === 'rejected') setError(toClientApiError(failure.reason))
      setLoading(false)
    })

    return () => {
      active = false
    }
  }, [requestVersion])

  const value = useMemo(
    () => ({ health, system, safety, loading, error, refresh }),
    [health, system, safety, loading, error, refresh],
  )
  return <SystemDataContext.Provider value={value}>{children}</SystemDataContext.Provider>
}
