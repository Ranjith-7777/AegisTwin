import { useContext } from 'react'

import {
  SimulationPlaybackContext,
  type SimulationPlaybackContextValue,
} from '../app/simulationPlaybackContext'

export function useSimulationPlayback(): SimulationPlaybackContextValue {
  const value = useContext(SimulationPlaybackContext)
  if (!value)
    throw new Error('useSimulationPlayback must be used inside SimulationPlaybackProvider')
  return value
}

/** Non-throwing variant for components that may render outside the provider. */
export function useOptionalSimulationPlayback(): SimulationPlaybackContextValue | null {
  return useContext(SimulationPlaybackContext)
}
