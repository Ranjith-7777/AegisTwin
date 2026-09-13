import { Gauge } from '../ui/Gauge'
import type { CommandCentreState } from '../../lib/commandCentre'

function riskBand(score: number): { label: string; tone: 'healthy' | 'warn' | 'danger' } {
  if (score >= 60) return { label: 'High', tone: 'danger' }
  if (score >= 30) return { label: 'Moderate', tone: 'warn' }
  return { label: 'Low', tone: 'healthy' }
}

/** Command Centre's primary visual: the existing weighted risk score, gauged. */
export function RiskGauge({
  state,
  hasEvidence,
}: {
  state: CommandCentreState
  hasEvidence: boolean
}) {
  const band = riskBand(state.riskScore)
  return (
    <section className="card" aria-label="Current risk">
      <div className="card-head">
        <h2 className="card-title">Current Risk</h2>
      </div>
      <div className="p-4">
        {hasEvidence ? (
          <>
            <Gauge value={state.riskScore} label={band.label} tone={band.tone} />
            <p className="mt-2 text-center text-xs text-slate-500">{state.riskBasis}</p>
          </>
        ) : (
          <>
            <Gauge value={0} label="No evidence" tone="healthy" valueLabel="—" />
            <p className="mt-2 text-center text-xs text-slate-500">
              No synthetic scenario has been replayed yet in this session.
            </p>
          </>
        )}
      </div>
    </section>
  )
}
