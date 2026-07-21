import { Database, Server } from 'lucide-react'

import { Card, CardContent, CardHeader } from '../ui/card'
import type { HealthResponse } from '../../types/api'

export function SystemStatusCard({ health }: { health: HealthResponse | null }) {
  const connected = health?.status === 'healthy' && health.database === 'connected'
  return (
    <Card>
      <CardHeader>
        <div>
          <p className="eyebrow">Foundation status</p>
          <h2 className="panel-title">Live system checks</h2>
        </div>
        <Server className="size-5 text-cyan-400" aria-hidden="true" />
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="status-row">
          <span>Backend API</span>
          <strong>{connected ? 'Connected' : 'Disconnected'}</strong>
        </div>
        <div className="status-row">
          <span className="flex items-center gap-2">
            <Database className="size-4" />
            Database
          </span>
          <strong>{health?.database ?? 'unknown'}</strong>
        </div>
        <div className="status-row">
          <span>Environment</span>
          <strong>{health?.environment ?? 'unavailable'}</strong>
        </div>
      </CardContent>
    </Card>
  )
}
