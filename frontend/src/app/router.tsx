import { Route, Routes } from 'react-router-dom'

import { DashboardLayout } from '../components/layout/DashboardLayout'
import { AuditTrailPage } from '../pages/AuditTrailPage'
import { DigitalTwinPage } from '../pages/DigitalTwinPage'
import { IncidentsPage } from '../pages/IncidentsPage'
import { MitrePage } from '../pages/MitrePage'
import { ModelAnalyticsPage } from '../pages/ModelAnalyticsPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { OverviewPage } from '../pages/OverviewPage'
import { ResponseCentrePage } from '../pages/ResponseCentrePage'
import { SettingsPage } from '../pages/SettingsPage'
import { TelemetryPage } from '../pages/TelemetryPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<DashboardLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="digital-twin" element={<DigitalTwinPage />} />
        <Route path="telemetry" element={<TelemetryPage />} />
        <Route path="incidents" element={<IncidentsPage />} />
        <Route path="mitre" element={<MitrePage />} />
        <Route path="response-centre" element={<ResponseCentrePage />} />
        <Route path="audit-trail" element={<AuditTrailPage />} />
        <Route path="model-analytics" element={<ModelAnalyticsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
