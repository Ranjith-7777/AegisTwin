import { useContext } from 'react'

import { SystemDataContext, type SystemDataContextValue } from '../app/systemDataContext'

export function useSystemData(): SystemDataContextValue {
  const value = useContext(SystemDataContext)
  if (!value) throw new Error('useSystemData must be used inside SystemDataProvider')
  return value
}
