import { Route, Routes } from 'react-router-dom'
import { lazy, Suspense, type ReactNode } from 'react'

import { DashboardLayout } from '../components/layout/DashboardLayout'
import { AuditTrailPage } from '../pages/AuditTrailPage'
import { IncidentsPage } from '../pages/IncidentsPage'
import { MitrePage } from '../pages/MitrePage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { OverviewPage } from '../pages/OverviewPage'
import { SettingsPage } from '../pages/SettingsPage'
import { TelemetryPage } from '../pages/TelemetryPage'

const DigitalTwinPage = lazy(() =>
  import('../pages/DigitalTwinPage').then((module) => ({ default: module.DigitalTwinPage })),
)
const ModelAnalyticsPage = lazy(() =>
  import('../pages/ModelAnalyticsPage').then((module) => ({ default: module.ModelAnalyticsPage })),
)
const PredictiveAnalyticsPage = lazy(() =>
  import('../pages/PredictiveAnalyticsPage').then((module) => ({
    default: module.PredictiveAnalyticsPage,
  })),
)
const ResponseCentrePage = lazy(() =>
  import('../pages/ResponseCentrePage').then((module) => ({
    default: module.ResponseCentrePage,
  })),
)

function LazyPage({ children }: { children: ReactNode }) {
  return <Suspense fallback={<p role="status">Loading dashboard module…</p>}>{children}</Suspense>
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<DashboardLayout />}>
        <Route index element={<OverviewPage />} />
        <Route
          path="digital-twin"
          element={
            <LazyPage>
              <DigitalTwinPage />
            </LazyPage>
          }
        />
        <Route path="telemetry" element={<TelemetryPage />} />
        <Route path="incidents" element={<IncidentsPage />} />
        <Route path="mitre" element={<MitrePage />} />
        <Route
          path="response-centre"
          element={
            <LazyPage>
              <ResponseCentrePage />
            </LazyPage>
          }
        />
        <Route path="audit-trail" element={<AuditTrailPage />} />
        <Route
          path="model-analytics"
          element={
            <LazyPage>
              <ModelAnalyticsPage />
            </LazyPage>
          }
        />
        <Route
          path="predictive-analytics"
          element={
            <LazyPage>
              <PredictiveAnalyticsPage />
            </LazyPage>
          }
        />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
