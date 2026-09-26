import { useSystemData } from './useSystemData'

export function useSystemStatus() {
  const { system, loading, error, refresh } = useSystemData()
  return { system, loading, error, refresh }
}
