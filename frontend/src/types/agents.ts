export type AgentSide = 'red' | 'blue'

export interface AgentDescriptor {
  agent_id: string
  display_name: string
  side: AgentSide
  role: string
  description: string
  implementation_type: string
  version: string
  input_types: string[]
  decision_type: string
  output_types: string[]
  next_agent: string | null
  synthetic: true
}

export interface AnalyticalSubsystemDescriptor {
  subsystem_id: string
  display_name: string
  description: string
  consumed_by: string[]
  synthetic: true
}

export interface AgentRegistry {
  agents: AgentDescriptor[]
  analytical_subsystems: AnalyticalSubsystemDescriptor[]
  total_agents: number
  red_agent_count: number
  blue_agent_count: number
  synthetic: true
}

export interface AgentTraceEntry {
  agent_id: string
  agent_name: string
  sequence: number
  timestamp: string
  input_summary: string
  decision_type: string
  decision: string
  rationale: string
  warnings: string[]
  resource_ids: string[]
  score: number | null
  next_agent: string | null
  status: string
  synthetic: true
}

export interface AgentTrace {
  orchestration_id: string
  entries: AgentTraceEntry[]
  stopped_reason: string | null
  synthetic: true
}
