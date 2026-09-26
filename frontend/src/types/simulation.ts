export type PlaybackState = 'idle' | 'playing' | 'paused' | 'stopped' | 'completed' | 'error'

export interface ScenarioStep {
  sequence: number
  offset_seconds: number
  description: string
  event_type: string
  action: string
  outcome: string
  severity: string
  source_type: string
  source_id: string
  destination_id: string | null
}

export interface SimulationScenario {
  scenario_id: string
  name: string
  description: string
  steps: ScenarioStep[]
  synthetic: true
}

export interface SimulationRunCreate {
  scenario_id: string
  seed: number
  start_time: string
  playback_speed: number
}

export interface SimulationRun {
  simulation_run_id: string
  scenario_id: string
  seed: number
  start_time: string
  playback_speed: number
  status: 'completed'
  event_count: number
  created_at: string
}

export interface TelemetryEvent {
  event_id: string
  scenario_id: string
  simulation_run_id: string
  timestamp: string
  event_type: string
  action: string
  outcome: string
  severity: 'informational' | 'low' | 'medium' | 'high' | 'critical'
  source_type: string
  source_id: string
  destination_id: string | null
  user_id: string | null
  device_id: string | null
  source_ip: string | null
  destination_ip: string | null
  privilege_level: string | null
  failed_attempts: number
  bytes_transferred: number
  process_name: string | null
  metadata: { synthetic: true; [key: string]: unknown }
  created_at: string
}

export interface TelemetryEventPage {
  items: TelemetryEvent[]
  page: number
  page_size: number
  total: number
  pages: number
}

export interface PlaybackMetadata {
  run: SimulationRun
  total_events: number
  first_event_timestamp: string | null
  last_event_timestamp: string | null
  simulated_duration_seconds: number
  default_playback_speed: number
  synthetic: true
  available_controls: string[]
}
