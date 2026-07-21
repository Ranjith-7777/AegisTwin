import { ShieldCheck } from 'lucide-react'

import { FALLBACK_SAFETY_MESSAGE } from '../../lib/constants'
import { useSafetyStatus } from '../../hooks/useSafetyStatus'

export function SimulationBanner() {
  const { safety } = useSafetyStatus()
  const backendMessage = safety?.simulation_only ? safety.message : null
  return (
    <div
      className="simulation-banner"
      role="status"
      aria-label="Simulation environment safety notice"
    >
      <ShieldCheck className="size-4 shrink-0" aria-hidden="true" />
      <p>
        <strong>SIMULATION ENVIRONMENT</strong>
        <span aria-hidden="true"> — </span>
        {backendMessage ?? FALLBACK_SAFETY_MESSAGE}
      </p>
    </div>
  )
}
