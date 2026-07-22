import { Route, Routes } from 'react-router-dom'
import { lazy, Suspense, type ReactNode } from 'react'

import { DashboardLayout } from '../components/layout/DashboardLayout'
import { IncidentsPage } from '../pages/IncidentsPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { OverviewPage } from '../pages/OverviewPage'
import { SettingsPage } from '../pages/SettingsPage'
import { TelemetryPage } from '../pages/TelemetryPage'

const MitrePage = lazy(() =>
  import('../pages/MitrePage').then((module) => ({ default: module.MitrePage })),
)
const AuditTrailPage = lazy(() =>
  import('../pages/AuditTrailPage').then((module) => ({ default: module.AuditTrailPage })),
)
const ResponseOperationsPage = lazy(() =>
  import('../pages/ResponseOperationsPage').then((module) => ({
    default: module.ResponseOperationsPage,
  })),
)

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
        <Route
          path="mitre"
          element={
            <LazyPage>
              <MitrePage />
            </LazyPage>
          }
        />
        <Route
          path="response-centre"
          element={
            <LazyPage>
              <ResponseCentrePage />
            </LazyPage>
          }
        />
        <Route
          path="audit-trail"
          element={
            <LazyPage>
              <AuditTrailPage />
            </LazyPage>
          }
        />
        <Route
          path="response-operations"
          element={
            <LazyPage>
              <ResponseOperationsPage />
            </LazyPage>
          }
        />
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
