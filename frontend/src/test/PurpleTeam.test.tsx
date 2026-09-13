import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { PurpleTeamPanel } from '../components/topology/PurpleTeamPanel'
import * as purpleTeamApi from '../services/purpleTeamApi'
import type { PurpleTeamExperiment, RedScenarioSummary } from '../types/purpleTeam'
import type { RedScenarioDefinition } from '../types/redScenario'

vi.mock('../services/purpleTeamApi')

const scenarios: RedScenarioSummary[] = [
  {
    scenario_id: 'credential-compromise',
    name: 'Cloud Credential Compromise Exercise',
    description: 'Repeated failures then a valid login.',
    is_red_agent_scenario: false,
    step_count: 2,
    mitre_technique_ids: ['T1078', 'T1110.001'],
    step_techniques: [],
    synthetic: true,
  },
]

const definition: RedScenarioDefinition = {
  scenario_id: 'credential-compromise',
  display_name: 'Cloud Credential Compromise Exercise',
  objective: 'Brute-force then log in with a valid account.',
  description: '2-step deterministic scenario exercising technique(s): T1078, T1110.001.',
  initial_access_point: 'external-user-01',
  high_value_objective: 'cloud-database-01',
  prerequisites: ['attacker-controlled foothold at external-user-01'],
  is_red_agent_scenario: false,
  steps: [],
  synthetic: true,
}

const experiment: PurpleTeamExperiment = {
  experiment_id: 'experiment-1',
  scenario_id: 'credential-compromise',
  scenario_name: 'Cloud Credential Compromise Exercise',
  mode: 'observe_only',
  seed: 84,
  simulation_run_id: 'run-1',
  model_id: 'model-1',
  status: 'completed',
  error: null,
  created_at: '2026-09-13T00:00:00Z',
  completed_at: '2026-09-13T00:01:00Z',
  synthetic: true,
  steps: [
    {
      step_result_id: 'step-1',
      experiment_id: 'experiment-1',
      step_sequence: 1,
      description: 'Repeated failed authentication',
      event_id: 'event-1',
      target_asset_id: 'api-gateway-01',
      expected_technique_id: 'T1110.001',
      expected_technique_name: 'Password Guessing',
      outcome: 'failed_precondition',
      detected: true,
      anomaly_score: 0.9,
      classification: 'anomalous',
      observed_technique_ids: ['T1110.001'],
      incident_candidate_id: 'candidate-1',
      response_recommendation_id: null,
      orchestration_id: null,
      orchestration_state: null,
      synthetic: true,
    },
    {
      step_result_id: 'step-2',
      experiment_id: 'experiment-1',
      step_sequence: 2,
      description: 'A step with no declared indicator',
      event_id: 'event-2',
      target_asset_id: 'application-pod-01',
      expected_technique_id: null,
      expected_technique_name: null,
      outcome: 'succeeded_synthetic',
      detected: false,
      anomaly_score: 0.1,
      classification: 'normal',
      observed_technique_ids: [],
      incident_candidate_id: null,
      response_recommendation_id: null,
      orchestration_id: null,
      orchestration_state: null,
      synthetic: true,
    },
  ],
  summary: {
    total_steps: 2,
    attempted_steps: 2,
    succeeded_synthetic_steps: 1,
    detected_steps: 1,
    missed_steps: 0,
    expected_detectable_steps: 1,
    detection_step_coverage: 1,
    mitre_techniques_exercised: ['T1110.001'],
    mitre_techniques_observed: ['T1110.001'],
    incident_created: true,
    first_detection_sequence: 1,
    response_recommendation_created: false,
    response_executed: false,
    verification_result: null,
    critical_assets_reached: ['cloud-database-01'],
    attack_path_context: {
      path_type: 'observed',
      source_asset_id: 'external-user-01',
      target_asset_id: 'cloud-database-01',
      hop_count: 2,
      score: 70,
      statement: 'observed path: external-user-01 -> api-gateway-01 -> cloud-database-01 (2 hops).',
      through_sequence_number: null,
      synthetic: true,
    },
    blast_radius_context: {
      compromised_asset_ids: ['external-user-01'],
      reachable_count: 4,
      critical_assets_at_risk: ['cloud-database-01'],
      trust_zones_reached: ['edge_zone', 'data_zone'],
      score: 42,
      mode: 'evidence_bound',
      through_sequence_number: 2,
      synthetic: true,
    },
    final_outcome: 'detected',
  },
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(purpleTeamApi.listRedScenarios).mockResolvedValue(scenarios)
  vi.mocked(purpleTeamApi.getScenarioDefinition).mockResolvedValue(definition)
  vi.mocked(purpleTeamApi.runPurpleTeamExperiment).mockResolvedValue(experiment)
})

describe('Purple Team panel', () => {
  it('explains the scenario before execution using the structured definition', async () => {
    render(<PurpleTeamPanel />)
    expect(await screen.findByText(definition.objective)).toBeInTheDocument()
    expect(screen.getByText('external-user-01')).toBeInTheDocument()
    expect(screen.getByText('cloud-database-01')).toBeInTheDocument()
  })

  it('shows a genuine in-progress state while the experiment request is in flight', async () => {
    let resolveRun: (value: PurpleTeamExperiment) => void = () => undefined
    vi.mocked(purpleTeamApi.runPurpleTeamExperiment).mockReturnValue(
      new Promise((resolve) => {
        resolveRun = resolve
      }),
    )
    render(<PurpleTeamPanel />)
    await userEvent.click(screen.getByRole('button', { name: 'Run experiment' }))
    expect(await screen.findByText(/Running experiment:/)).toBeInTheDocument()
    resolveRun(experiment)
    await waitFor(() => {
      expect(screen.queryByText(/Running experiment:/)).not.toBeInTheDocument()
    })
  })

  it('uses expected_detectable_steps, not total_steps, as the coverage denominator', async () => {
    render(<PurpleTeamPanel />)
    await userEvent.click(screen.getByRole('button', { name: 'Run experiment' }))
    await waitFor(() => {
      expect(purpleTeamApi.runPurpleTeamExperiment).toHaveBeenCalled()
    })
    // missed_steps / expected_detectable_steps = 0 / 1, never 0 / total_steps (2)
    expect(await screen.findByText('0 / 1')).toBeInTheDocument()
    expect(screen.queryByText('0 / 2')).not.toBeInTheDocument()
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('distinguishes detected from missed steps in the timeline', async () => {
    render(<PurpleTeamPanel />)
    await userEvent.click(screen.getByRole('button', { name: 'Run experiment' }))
    const rows = await screen.findAllByRole('row')
    const detectedRow = rows.find((row) => row.textContent.includes('Repeated failed'))
    const missedRow = rows.find((row) => row.textContent.includes('no declared indicator'))
    expect(detectedRow).toBeDefined()
    expect(missedRow).toBeDefined()
    expect(detectedRow?.textContent ?? '').toContain('Yes')
    expect(missedRow?.textContent ?? '').toContain('No')
  })

  it('renders the real attack-path and blast-radius context, never a placeholder', async () => {
    render(<PurpleTeamPanel />)
    await userEvent.click(screen.getByRole('button', { name: 'Run experiment' }))
    expect(
      await screen.findByText(
        'observed path: external-user-01 -> api-gateway-01 -> cloud-database-01 (2 hops).',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText(/4 reachable/)).toBeInTheDocument()
    expect(screen.getByText(/evidence bound/)).toBeInTheDocument()
  })

  it('surfaces a backend error without crashing', async () => {
    vi.mocked(purpleTeamApi.runPurpleTeamExperiment).mockRejectedValue(new Error('boom'))
    render(<PurpleTeamPanel />)
    await userEvent.click(screen.getByRole('button', { name: 'Run experiment' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The AegisArena backend is unavailable.',
    )
  })
})
