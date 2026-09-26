import { LiveAnomalyDashboard } from '../components/detection/LiveAnomalyDashboard'
import { LiveEventStream } from '../components/simulation/LiveEventStream'
import { RunHistory } from '../components/simulation/RunHistory'
import { SimulationControlPanel } from '../components/simulation/SimulationControlPanel'

export function TelemetryPage() {
  return (
    <div className="space-y-5">
      <header className="page-heading">
        <h1>Live Telemetry</h1>
        <p>Replay persisted deterministic events. No real infrastructure is contacted.</p>
      </header>
      <section className="dashboard-grid">
        <SimulationControlPanel />
        <LiveEventStream expanded />
        <LiveAnomalyDashboard />
        <RunHistory />
      </section>
    </div>
  )
}
