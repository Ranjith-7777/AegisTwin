import { useSystemData } from './useSystemData'

export function useSystemHealth() {
  const { health, loading, error, refresh } = useSystemData()
  return { health, loading, error, refresh }
}
