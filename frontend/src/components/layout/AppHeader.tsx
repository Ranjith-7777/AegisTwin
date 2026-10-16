import { LogOut, Menu, RefreshCw, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useOptionalAutonomyWorkflow } from '../../hooks/useAutonomyWorkflow'
import { useSafetyStatus } from '../../hooks/useSafetyStatus'
import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { useSystemData } from '../../hooks/useSystemData'
import { FALLBACK_SAFETY_MESSAGE } from '../../lib/constants'
import { cn } from '../../lib/utils'
import { Tip } from '../ui/panel'
import { AutonomyModePill } from '../workflow/AutonomyModePill'
import { GlobalSearch } from './GlobalSearch'
import { NotificationsMenu } from './NotificationsMenu'

function titleCase(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export function AppHeader({ onMenu }: { onMenu: () => void }) {
  const { health, loading, refresh } = useSystemData()
  const { safety } = useSafetyStatus()
  const playback = useSimulationPlayback()
  const workflow = useOptionalAutonomyWorkflow()
  const connected = health?.status === 'healthy' && health.database === 'connected'
  const environment = health?.environment ?? workflow?.session?.environment ?? null
  const run = playback.activeRun
  const scenario = run
    ? (playback.scenarios.find((item) => item.scenario_id === run.scenario_id)?.name ??
      run.scenario_id)
    : null
  const session = workflow?.session ?? null
  const identity = !session
    ? null
    : session.auth_mode === 'development_bypass'
      ? { name: 'Local operator', initials: 'LO' }
      : session.auth_mode === 'easy_auth'
        ? { name: 'Signed-in user', initials: 'SU' }
        : { name: 'Anonymous viewer', initials: 'AV' }
  return (
    <header className="app-header">
      <div className="header-left">
        <button
          type="button"
          className="icon-btn menu-toggle"
          onClick={onMenu}
          aria-label="Open navigation"
        >
          <Menu aria-hidden="true" />
        </button>
        <Tip
          label={
            connected
              ? `Backend healthy · database connected · ENVIRONMENT=${environment ?? 'unknown'}`
              : 'The backend API or its database is not reachable.'
          }
        >
          <span
            className={cn('header-pill', connected ? 'is-ok' : 'is-down')}
            role="status"
            aria-label={`Backend ${connected ? 'healthy' : 'unavailable'}, environment ${environment ?? 'unknown'}`}
          >
            <span className="chip-dot" aria-hidden="true" />
            {loading && !health
              ? 'Connecting…'
              : environment
                ? titleCase(environment)
                : 'Backend unavailable'}
          </span>
        </Tip>
        <Tip label={safety?.simulation_only ? safety.message : FALLBACK_SAFETY_MESSAGE}>
          <span className="header-pill is-safety" role="status" aria-label="Simulation-only safety">
            <ShieldCheck aria-hidden="true" />
            Simulation only
          </span>
        </Tip>
        {run ? (
          <span className="header-pill is-run" title={`Run ${run.simulation_run_id}`}>
            <span
              className={`status-dot ${playback.playbackState === 'playing' ? 'is-live text-[var(--danger)]' : 'text-[#94a3b8]'}`}
              aria-hidden="true"
            />
            {scenario} · seed {run.seed}
          </span>
        ) : null}
      </div>
      <GlobalSearch />
      <div className="header-right">
        {workflow?.autonomy ? <AutonomyModePill mode={workflow.autonomy.mode} /> : null}
        <NotificationsMenu />
        <button
          type="button"
          className="icon-btn"
          onClick={refresh}
          disabled={loading}
          aria-label="Refresh system status"
        >
          <RefreshCw
            className={loading ? 'animate-spin motion-reduce:animate-none' : ''}
            aria-hidden="true"
          />
        </button>
        {session && identity ? (
          <Tip
            label={
              session.auth_mode === 'development_bypass'
                ? 'Development/demo role from AUTH_DEV_BYPASS_ROLE - never permitted in production.'
                : session.auth_mode === 'easy_auth'
                  ? 'Signed in through Azure Container Apps Easy Auth.'
                  : 'Anonymous read-only viewer: actions that change state are disabled.'
            }
          >
            <span className="header-user" aria-label={`Role ${session.role}`}>
              <span className="avatar" aria-hidden="true">
                {identity.initials}
              </span>
              <span className="header-user-text">
                <strong>{identity.name}</strong>
                <span>
                  {titleCase(session.role.toLowerCase())}
                  {session.auth_mode === 'development_bypass' ? ' · dev role' : ''}
                </span>
              </span>
            </span>
          </Tip>
        ) : null}
        {session?.auth_mode === 'easy_auth' ? (
          <a
            className="icon-btn"
            href="/.auth/logout?post_logout_redirect_uri=%2F"
            aria-label="Sign out"
            title="Sign out"
          >
            <LogOut aria-hidden="true" />
          </a>
        ) : (
          <Link className="icon-btn" to="/" aria-label="Return to public site" title="Public site">
            <LogOut aria-hidden="true" />
          </Link>
        )}
      </div>
    </header>
  )
}
