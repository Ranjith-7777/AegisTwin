import { Menu, RefreshCw, Server, ShieldCheck } from 'lucide-react'

import { useSystemData } from '../../hooks/useSystemData'
import { AgentStatusIndicator } from '../dashboard/AgentStatusIndicator'
import { Button } from '../ui/button'

export function AppHeader({ onMenu }: { onMenu: () => void }) {
  const { health, system, loading, refresh } = useSystemData()
  const connected = health?.status === 'healthy' && health.database === 'connected'
  const operational = connected && system?.operational === true
  return (
    <header className="app-header">
      <div className="flex min-w-0 items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={onMenu}
          aria-label="Open navigation"
        >
          <Menu className="size-5" />
        </Button>
        <div className="min-w-0">
          <p className="eyebrow">Operations console</p>
          <p className="truncate text-sm font-medium text-slate-200">
            Agentic Cyber-Resilience Digital Twin
          </p>
        </div>
      </div>
      <div className="header-statuses">
        <span className={connected ? 'status-chip is-healthy' : 'status-chip is-offline'}>
          <Server className="size-3.5" />
          Backend: {loading ? 'Checking' : connected ? 'Connected' : 'Disconnected'}
        </span>
        <span className="status-chip is-simulation">
          <ShieldCheck className="size-3.5" />
          Mode: Simulation
        </span>
        <span className={operational ? 'status-chip is-healthy' : 'status-chip'}>
          System: {operational ? 'Operational' : 'Unavailable'}
        </span>
        <AgentStatusIndicator
          count={system?.agents_online ?? 0}
          live={connected && system !== null}
        />
        <span className="status-chip hidden xl:inline-flex">
          Environment: {health?.environment ?? 'unavailable'}
        </span>
        <Button
          variant="outline"
          size="icon"
          onClick={refresh}
          disabled={loading}
          aria-label="Refresh system status"
        >
          <RefreshCw
            className={loading ? 'size-4 animate-spin motion-reduce:animate-none' : 'size-4'}
          />
        </Button>
      </div>
    </header>
  )
}
