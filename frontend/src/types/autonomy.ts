export type AutonomyMode = 'observe' | 'recommend' | 'approval_required' | 'autonomous'

export interface AutonomyConfig {
  mode: AutonomyMode
  description: string
  updated_by: string
  updated_at: string
  synthetic: true
}
