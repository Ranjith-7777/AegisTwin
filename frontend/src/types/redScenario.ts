export interface RedScenarioStepDefinition {
  step_id: string
  sequence: number
  name: string
  description: string
  action_type: string
  source_asset_id: string
  target_asset_id: string | null
  prerequisites: string[]
  expected_technique_ids: string[]
  expected_event_type: string
  success_condition: string
  synthetic: true
}

export interface RedScenarioDefinition {
  scenario_id: string
  display_name: string
  objective: string
  description: string
  initial_access_point: string
  high_value_objective: string | null
  prerequisites: string[]
  is_red_agent_scenario: boolean
  steps: RedScenarioStepDefinition[]
  synthetic: true
}
