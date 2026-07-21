import { useSystemData } from './useSystemData'

export function useSafetyStatus() {
  const { safety, loading, error, refresh } = useSystemData()
  return { safety, loading, error, refresh }
}
