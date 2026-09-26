import { createContext } from 'react'

import type {
  ClientApiError,
  HealthResponse,
  SafetyResponse,
  SystemStatusResponse,
} from '../types/api'

export interface SystemDataContextValue {
  health: HealthResponse | null
  system: SystemStatusResponse | null
  safety: SafetyResponse | null
  loading: boolean
  error: ClientApiError | null
  refresh: () => void
}

export const SystemDataContext = createContext<SystemDataContextValue | null>(null)
