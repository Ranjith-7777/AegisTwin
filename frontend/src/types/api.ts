export interface HealthResponse {
  status: 'healthy' | 'unhealthy'
  service: string
  environment: string
  simulation_only: boolean
  database: 'connected' | 'disconnected'
}

export interface SystemStatusResponse {
  system_name: string
  mode: 'simulation'
  operational: boolean
  active_incidents: number
  agents_online: number
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
