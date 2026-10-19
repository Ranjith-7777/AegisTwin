import { Route, Routes } from 'react-router-dom'
import { lazy, Suspense, type ReactNode } from 'react'

import { IncidentsPage } from '../pages/IncidentsPage'
import { LandingPage } from '../pages/LandingPage'
import { LoginPage } from '../pages/LoginPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { OverviewPage } from '../pages/OverviewPage'
import { SettingsPage } from '../pages/SettingsPage'
import { TelemetryPage } from '../pages/TelemetryPage'
import { ProtectedConsole } from './ProtectedConsole'

const MitrePage = lazy(() =>
  import('../pages/MitrePage').then((module) => ({ default: module.MitrePage })),
)
const AuditTrailPage = lazy(() =>
  import('../pages/AuditTrailPage').then((module) => ({ default: module.AuditTrailPage })),
)

const DigitalTwinPage = lazy(() =>
  import('../pages/DigitalTwinPage').then((module) => ({ default: module.DigitalTwinPage })),
)
const WorkflowPage = lazy(() =>
  import('../pages/WorkflowPage').then((module) => ({ default: module.WorkflowPage })),
)
const RedAgentOverviewPage = lazy(() =>
  import('../pages/RedAgentOverviewPage').then((module) => ({
    default: module.RedAgentOverviewPage,
  })),
)
const ModelAnalyticsPage = lazy(() =>
  import('../pages/ModelAnalyticsPage').then((module) => ({ default: module.ModelAnalyticsPage })),
)
const PredictiveAnalyticsPage = lazy(() =>
  import('../pages/PredictiveAnalyticsPage').then((module) => ({
    default: module.PredictiveAnalyticsPage,
  })),
)
const BlueAgentOverviewPage = lazy(() =>
  import('../pages/blueAgent/BlueAgentOverviewPage').then((module) => ({
    default: module.BlueAgentOverviewPage,
  })),
)
const AgentWorkflowPage = lazy(() =>
  import('../pages/blueAgent/AgentWorkflowPage').then((module) => ({
    default: module.AgentWorkflowPage,
  })),
)
const ResponsePlansPage = lazy(() =>
  import('../pages/blueAgent/ResponsePlansPage').then((module) => ({
    default: module.ResponsePlansPage,
  })),
)
const PoliciesPage = lazy(() =>
  import('../pages/blueAgent/PoliciesPage').then((module) => ({ default: module.PoliciesPage })),
)
const VerificationPage = lazy(() =>
  import('../pages/blueAgent/VerificationPage').then((module) => ({
    default: module.VerificationPage,
  })),
)
const EvaluationOverviewPage = lazy(() =>
  import('../pages/evaluation/EvaluationOverviewPage').then((module) => ({
    default: module.EvaluationOverviewPage,
  })),
)
const ExperimentListPage = lazy(() =>
  import('../pages/evaluation/ExperimentListPage').then((module) => ({
    default: module.ExperimentListPage,
  })),
)
const ExperimentDetailPage = lazy(() =>
  import('../pages/evaluation/ExperimentDetailPage').then((module) => ({
    default: module.ExperimentDetailPage,
  })),
)
const ComparisonPage = lazy(() =>
  import('../pages/evaluation/ComparisonPage').then((module) => ({
    default: module.ComparisonPage,
  })),
)
const AggregatePage = lazy(() =>
  import('../pages/evaluation/AggregatePage').then((module) => ({
    default: module.AggregatePage,
  })),
)
const BatchesPage = lazy(() =>
  import('../pages/evaluation/BatchesPage').then((module) => ({ default: module.BatchesPage })),
)
const DataSourcesPage = lazy(() =>
  import('../pages/DataSourcesPage').then((module) => ({ default: module.DataSourcesPage })),
)
const ExperimentReportPage = lazy(() =>
  import('../pages/evaluation/ExperimentReportPage').then((module) => ({
    default: module.ExperimentReportPage,
  })),
)

function LazyPage({ children }: { children: ReactNode }) {
  return (
    <Suspense
      fallback={
        <p role="status" className="flex items-center gap-2 text-[0.8rem] text-[var(--text-faint)]">
          <span className="spinner" aria-hidden="true" /> Loading module…
        </p>
      }
    >
      {children}
    </Suspense>
  )
}

export function AppRoutes() {
  return (
    <Routes>
      <Route index element={<LandingPage />} />
      <Route path="login" element={<LoginPage />} />
      <Route element={<ProtectedConsole />}>
        <Route path="app" element={<OverviewPage />} />
        <Route
          path="workflow"
          element={
            <LazyPage>
              <WorkflowPage />
            </LazyPage>
          }
        />
        <Route
          path="digital-twin"
          element={
            <LazyPage>
              <DigitalTwinPage key="topology" />
            </LazyPage>
          }
        />
        <Route
          path="digital-twin/attack-paths"
          element={
            <LazyPage>
              <DigitalTwinPage key="attack-paths" initialTab="attack-paths" />
            </LazyPage>
          }
        />
        <Route
          path="digital-twin/blast-radius"
          element={
            <LazyPage>
              <DigitalTwinPage key="blast-radius" initialTab="blast-radius" />
            </LazyPage>
          }
        />
        <Route
          path="digital-twin/purple-team"
          element={
            <LazyPage>
              <DigitalTwinPage key="purple-team" initialTab="purple-team" />
            </LazyPage>
          }
        />
        <Route
          path="red-agent"
          element={
            <LazyPage>
              <RedAgentOverviewPage />
            </LazyPage>
          }
        />
        <Route path="telemetry" element={<TelemetryPage />} />
        <Route
          path="data-sources"
          element={
            <LazyPage>
              <DataSourcesPage />
            </LazyPage>
          }
        />
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
          path="audit-trail"
          element={
            <LazyPage>
              <AuditTrailPage />
            </LazyPage>
          }
        />
        <Route
          path="blue-agent/overview"
          element={
            <LazyPage>
              <BlueAgentOverviewPage />
            </LazyPage>
          }
        />
        <Route
          path="blue-agent/agent-workflow"
          element={
            <LazyPage>
              <AgentWorkflowPage />
            </LazyPage>
          }
        />
        <Route
          path="blue-agent/response-plans"
          element={
            <LazyPage>
              <ResponsePlansPage />
            </LazyPage>
          }
        />
        <Route
          path="blue-agent/policies"
          element={
            <LazyPage>
              <PoliciesPage />
            </LazyPage>
          }
        />
        <Route
          path="blue-agent/verification"
          element={
            <LazyPage>
              <VerificationPage />
            </LazyPage>
          }
        />
        <Route
          path="evaluation"
          element={
            <LazyPage>
              <EvaluationOverviewPage />
            </LazyPage>
          }
        />
        <Route
          path="evaluation/experiments"
          element={
            <LazyPage>
              <ExperimentListPage />
            </LazyPage>
          }
        />
        <Route
          path="evaluation/experiments/:experimentId"
          element={
            <LazyPage>
              <ExperimentDetailPage />
            </LazyPage>
          }
        />
        <Route
          path="evaluation/experiments/:experimentId/report"
          element={
            <LazyPage>
              <ExperimentReportPage />
            </LazyPage>
          }
        />
        <Route
          path="evaluation/compare"
          element={
            <LazyPage>
              <ComparisonPage />
            </LazyPage>
          }
        />
        <Route
          path="evaluation/aggregate"
          element={
            <LazyPage>
              <AggregatePage />
            </LazyPage>
          }
        />
        <Route
          path="evaluation/batches"
          element={
            <LazyPage>
              <BatchesPage />
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
