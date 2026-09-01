export interface HealthResponse {
  status: 'healthy' | 'unhealthy'
  service: string
  environment: string
  simulation_only: boolean
  database: 'connected' | 'disconnected'
}

export interface SystemStatusResponse {
  system_name: string
  system_tagline?: string
  mode: 'simulation'
  operational: boolean
  active_incidents: number
  agents_online: number
  red_agent_runs?: number
  blue_agent_orchestrations?: number
  version?: string
  git_commit?: string | null
  build_mode?: string
  demo_mode?: boolean
  database_revision?: string
  synthetic_only?: boolean
  benchmark_report_timestamp?: string | null
}

export interface SafetyResponse {
  simulation_only: boolean
  real_world_actions_enabled: false
  external_targets_allowed: false
  message: string
}

export interface ApiErrorResponse {
  error_code: string
  message: string
  correlation_id: string
}

export interface ClientApiError {
  message: string
  correlationId?: string
}
