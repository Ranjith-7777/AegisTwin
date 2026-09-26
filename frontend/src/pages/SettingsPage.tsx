import { useSystemData } from '../hooks/useSystemData'
import { APP_FULL_NAME, DEPLOYMENT_ENV } from '../lib/constants'
import { Card, CardContent, CardHeader } from '../components/ui/card'
import { SystemStatusCard } from '../components/dashboard/SystemStatusCard'

export function SettingsPage() {
  const { health, system } = useSystemData()
  return (
    <div className="space-y-6">
      <header className="page-heading">
        <h1>System Information</h1>
        <p>
          Safe build and simulation status. No paths, credentials, usernames, or machine names are
          exposed.
        </p>
      </header>
      <SystemStatusCard health={health} />
      <Card>
        <CardHeader>
          <h2 className="panel-title">About {APP_FULL_NAME}</h2>
          <span className="status-chip is-simulation">Synthetic only</span>
        </CardHeader>
        <CardContent>
          <dl className="status-row">
            <div>
              <dt>Version</dt>
              <dd>{system?.version ?? 'development'}</dd>
            </div>
            <div>
              <dt>Git commit</dt>
              <dd>{system?.git_commit ?? 'not supplied'}</dd>
            </div>
            <div>
              <dt>Build mode</dt>
              <dd>{system?.build_mode ?? DEPLOYMENT_ENV}</dd>
            </div>
            <div>
              <dt>Judge Demo Mode</dt>
              <dd>{system?.demo_mode ? 'enabled' : 'disabled'}</dd>
            </div>
            <div>
              <dt>Backend connectivity</dt>
              <dd>{health?.status === 'healthy' ? 'connected' : 'unavailable'}</dd>
            </div>
            <div>
              <dt>Database migration</dt>
              <dd>{system?.database_revision ?? 'unavailable'}</dd>
            </div>
            <div>
              <dt>Safety</dt>
              <dd>
                {system?.synthetic_only === false ? 'invalid configuration' : 'simulation only'}
              </dd>
            </div>
            <div>
              <dt>Benchmark timestamp</dt>
              <dd>{system?.benchmark_report_timestamp ?? 'not supplied'}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>
    </div>
  )
}
