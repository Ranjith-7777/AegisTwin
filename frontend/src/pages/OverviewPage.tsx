import { useSystemData } from '../hooks/useSystemData'
import { ErrorState } from '../components/common/ErrorState'
import { DigitalTwinPlaceholder } from '../components/dashboard/DigitalTwinPlaceholder'
import { LiveEventStream } from '../components/simulation/LiveEventStream'
import { SimulationControlPanel } from '../components/simulation/SimulationControlPanel'
import { MetricCard } from '../components/dashboard/MetricCard'
import { MitreTimelinePlaceholder } from '../components/dashboard/MitreTimelinePlaceholder'
import { ResponseRecommendationPlaceholder } from '../components/dashboard/ResponseRecommendationPlaceholder'
import { SystemStatusCard } from '../components/dashboard/SystemStatusCard'
import { ThreatActivityChart } from '../components/dashboard/ThreatActivityChart'
import { LiveAnomalyDashboard } from '../components/detection/LiveAnomalyDashboard'
import { getDashboardMetrics } from '../mocks/dashboardMetrics'

export function OverviewPage() {
  const { health, system, error, refresh } = useSystemData()
  const metrics = getDashboardMetrics(system?.active_incidents ?? 0, system?.agents_online ?? 0)
  return (
    <div className="space-y-6">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Command overview</p>
          <h1>Operational posture</h1>
          <p>Foundation-level visibility for the simulation environment.</p>
        </div>
        <span className="live-label">
          <span />
          System Operational
        </span>
      </header>
      {error ? (
        <ErrorState
          message="Some backend status checks are unavailable. Dashboard placeholders remain available."
          correlationId={error.correlationId}
          onRetry={refresh}
        />
      ) : null}
      <section className="metric-grid" aria-label="System metrics">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} metric={metric} />
        ))}
      </section>
      <section className="dashboard-grid">
        <SimulationControlPanel />
        <LiveEventStream />
        <LiveAnomalyDashboard />
        <DigitalTwinPlaceholder />
        <SystemStatusCard health={health} />
        <ThreatActivityChart />
        <MitreTimelinePlaceholder />
        <ResponseRecommendationPlaceholder />
      </section>
    </div>
  )
}
