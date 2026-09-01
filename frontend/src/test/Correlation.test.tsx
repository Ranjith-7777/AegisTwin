import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderApp } from './test-utils'
import * as correlationApi from '../services/correlationApi'
import * as detectionApi from '../services/detectionApi'
import * as simulationApi from '../services/simulationApi'
import * as systemApi from '../services/systemApi'
import { parsePlaybackEnvelope } from '../types/playback'

vi.mock('../services/correlationApi')
vi.mock('../services/detectionApi')
vi.mock('../services/simulationApi')
vi.mock('../services/systemApi')

const run = {
  simulation_run_id: 'run-1',
  scenario_id: 'staged-compromise-demo',
  seed: 1,
  start_time: '2026-07-21T09:00:00Z',
  playback_speed: 10,
  status: 'completed' as const,
  event_count: 12,
  created_at: '2026-07-21T09:00:00Z',
}
const technique = {
  technique_id: 'T1110.001',
  name: 'Password Guessing',
  tactics: ['Credential Access'],
  description: 'Repeated synthetic guesses.',
  mapping_conditions: 'At least five failures.',
  catalogue_version: 'v1',
  source_name: 'local',
  reference_date: '2026-07-22',
  synthetic_demo_applicable: true,
  synthetic: true as const,
}
const candidate = {
  incident_candidate_id: 'candidate-1',
  simulation_run_id: run.simulation_run_id,
  model_id: 'model-1',
  title: 'Related unusual synthetic activity',
  correlation_state: 'monitoring' as const,
  priority: 'low',
  correlation_score: 0.3,
  component_scores: {},
  first_sequence_number: 5,
  latest_sequence_number: 6,
  primary_user_id: 'synthetic-user',
  primary_device_id: 'synthetic-device',
  involved_asset_ids: ['api-gateway-01'],
  observed_tactic_ids: ['Credential Access'],
  observed_technique_ids: ['T1110.001'],
  evidence_count: 2,
  synthetic: true as const,
}

beforeEach(() => {
  vi.mocked(systemApi.getHealth).mockResolvedValue({
    status: 'healthy',
    service: 'AegisTwin API',
    environment: 'test',
    simulation_only: true,
    database: 'connected',
  })
  vi.mocked(systemApi.getSystemStatus).mockResolvedValue({
    system_name: 'AegisTwin',
    mode: 'simulation',
    operational: true,
    active_incidents: 0,
    agents_online: 0,
  })
  vi.mocked(systemApi.getSafetyStatus).mockResolvedValue({
    simulation_only: true,
    real_world_actions_enabled: false,
    external_targets_allowed: false,
    message: 'Synthetic only',
  })
  vi.mocked(simulationApi.getScenarios).mockResolvedValue([])
  vi.mocked(simulationApi.getSimulationRuns).mockResolvedValue([run])
  vi.mocked(detectionApi.getDetectionModels).mockResolvedValue([])
  vi.mocked(correlationApi.getMitreTechniques).mockResolvedValue([technique])
  vi.mocked(correlationApi.getRunTechniques).mockResolvedValue({
    items: [],
    page: 1,
    page_size: 50,
    total: 0,
    pages: 0,
  })
  vi.mocked(correlationApi.getRunIncidents).mockResolvedValue({
    items: [candidate],
    page: 1,
    page_size: 50,
    total: 1,
    pages: 1,
  })
  vi.mocked(correlationApi.getIncidentEvidence).mockResolvedValue([])
})

describe('synthetic correlation UI', () => {
  it('defaults correlation off and only reveals it with detection', async () => {
    renderApp('/telemetry')
    expect(screen.queryByRole('checkbox', { name: 'Enable correlation' })).not.toBeInTheDocument()
    await userEvent.click(
      await screen.findByRole('checkbox', { name: 'Enable anomaly assessment' }),
    )
    expect(screen.getByRole('checkbox', { name: 'Enable correlation' })).not.toBeChecked()
  })
  it('renders the local MITRE catalogue without fabricated observations', async () => {
    renderApp('/mitre')
    expect(
      await screen.findByRole('heading', { name: 'MITRE ATT&CK', level: 1 }),
    ).toBeInTheDocument()
    expect(await screen.findByText(/T1110.001/)).toBeInTheDocument()
    expect(screen.getByText(/unsupported or unmapped events/i)).toBeInTheDocument()
  })
  it('renders incident candidate listing and safely rejects malformed messages', async () => {
    renderApp('/incidents')
    expect(await screen.findByRole('heading', { name: 'Incidents', level: 1 })).toBeInTheDocument()
    await userEvent.selectOptions(
      screen.getByLabelText('Incident candidate run'),
      run.simulation_run_id,
    )
    expect(await screen.findByText('Related unusual synthetic activity')).toBeInTheDocument()
    expect(
      parsePlaybackEnvelope({
        message_type: 'incident_candidate_update',
        run_id: 'run-1',
        sequence_number: 1,
        server_timestamp: '2026-07-22T00:00:00Z',
        synthetic: true,
        payload: { synthetic: true },
      }),
    ).toBeNull()
  })
})
