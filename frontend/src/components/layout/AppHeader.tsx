import { Menu, RefreshCw, Shield } from 'lucide-react'

import { useSystemData } from '../../hooks/useSystemData'
import { useSafetyStatus } from '../../hooks/useSafetyStatus'
import { APP_NAME, FALLBACK_SAFETY_MESSAGE } from '../../lib/constants'
import { Button } from '../ui/button'

export function AppHeader({ onMenu }: { onMenu: () => void }) {
  const { health, system, loading, refresh } = useSystemData()
  const { safety } = useSafetyStatus()
  const connected = health?.status === 'healthy' && health.database === 'connected'
  const operational = connected && system?.operational === true
  return (
    <header className="app-header">
      <div className="flex min-w-0 items-center gap-2.5">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={onMenu}
          aria-label="Open navigation"
        >
          <Menu className="size-5" />
        </Button>
        <span className="brand-mark" aria-hidden="true">
          <Shield className="size-[1.05rem]" />
        </span>
        <p className="brand-name">{APP_NAME}</p>
        <span className="chip chip-accent">Simulation Mode</span>
      </div>
      <div className="header-statuses">
        <span
          className="chip chip-muted"
          role="status"
          aria-label="Simulation environment safety notice"
          title={safety?.simulation_only ? safety.message : FALLBACK_SAFETY_MESSAGE}
        >
          Synthetic Environment
        </span>
        <span className={connected ? 'chip chip-healthy' : 'chip chip-danger'}>
          <span className="chip-dot" aria-hidden="true" />
          Backend {loading ? 'checking' : connected ? 'connected' : 'disconnected'}
        </span>
        <span className={operational ? 'chip chip-healthy' : 'chip chip-warn'}>
          <span className="chip-dot" aria-hidden="true" />
          System {operational ? 'operational' : 'unavailable'}
        </span>
        <Button
          variant="ghost"
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
