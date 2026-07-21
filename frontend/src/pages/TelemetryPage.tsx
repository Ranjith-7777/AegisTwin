import { LiveEventStream } from '../components/simulation/LiveEventStream'
import { RunHistory } from '../components/simulation/RunHistory'
import { SimulationControlPanel } from '../components/simulation/SimulationControlPanel'

export function TelemetryPage() {
  return (
    <div className="space-y-6">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Phase 3B · Simulation only</p>
          <h1>Live Telemetry</h1>
          <p>Replay persisted deterministic events. No real infrastructure is contacted.</p>
        </div>
      </header>
      <section className="dashboard-grid">
        <SimulationControlPanel />
        <LiveEventStream expanded />
        <RunHistory />
      </section>
    </div>
  )
}
