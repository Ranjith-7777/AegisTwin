import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderApp } from './test-utils'
import * as detectionApi from '../services/detectionApi'
import * as simulationApi from '../services/simulationApi'
import * as systemApi from '../services/systemApi'
import * as topologyApi from '../services/topologyApi'
import type { SimulationRun } from '../types/simulation'
import type { RunTopologyState, TopologySnapshot } from '../types/topology'

vi.mock('../services/systemApi')
vi.mock('../services/simulationApi')
vi.mock('../services/detectionApi')
vi.mock('../services/topologyApi')

const health = {
  status: 'healthy',
  service: 'AegisArena API',
  environment: 'test',
  simulation_only: true,
  database: 'connected',
} as const
const safety = {
  simulation_only: true,
  real_world_actions_enabled: false,
  external_targets_allowed: false,
  message: 'Backend confirms synthetic telemetry only.',
} as const

const snapshot: TopologySnapshot = {
  topology_version: 'aegisarena-cloud-topology-v1',
  nodes: [
    {
      asset_id: 'api-gateway-01',
      display_name: 'API Gateway',
      asset_type: 'load_balancer',
      zone: 'edge_zone',
      sensitivity: 'restricted',
      criticality: 'high',
      description: 'Synthetic edge gateway.',
      synthetic: true,
      metadata: {},
    },
  ],
  edges: [],
  generated_at: '2026-07-22T00:00:00Z',
  synthetic: true,
}

const knownRun: SimulationRun = {
  simulation_run_id: '31208de6-3573-57f5-a315-0e09eaacef95',
  scenario_id: 'staged-compromise-demo',
  seed: 84,
  start_time: '2026-07-21T09:00:00Z',
  playback_speed: 50,
  status: 'completed',
  event_count: 12,
  created_at: '2026-07-21T09:00:00Z',
}

const runState: RunTopologyState = {
  simulation_run_id: knownRun.simulation_run_id,
  state_version: 'live-topology-state-v1',
  model_id: null,
  observed_asset_ids: [],
  observed_edge_ids: [],
  correlated_asset_ids: [],
  correlated_edge_ids: [],
  predicted_asset_ids: [],
  predicted_edge_ids: [],
  anomalous_observed_asset_ids: [],
  anomalous_observed_edge_ids: [],
  unexpected_observed_edge_ids: [],
  event_mappings: [],
  predicted_paths: [],
  current_sequence_limit: 1,
  synthetic: true,
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(systemApi.getHealth).mockResolvedValue(health)
  vi.mocked(systemApi.getSafetyStatus).mockResolvedValue(safety)
  vi.mocked(systemApi.getSystemStatus).mockResolvedValue({
    system_name: 'AegisArena',
    system_tagline: 'Cloud Cyber Defense Range',
    mode: 'simulation',
    operational: true,
    active_incidents: 0,
    agents_online: 8,
    red_agent_runs: 0,
    blue_agent_orchestrations: 0,
    version: '0.9.0',
    git_commit: 'abcdef1',
    build_mode: 'production',
    demo_mode: true,
    database_revision: '20260817_0009',
    synthetic_only: true,
    benchmark_report_timestamp: null,
  })
  vi.mocked(simulationApi.getScenarios).mockResolvedValue([])
  vi.mocked(simulationApi.getSimulationRuns).mockResolvedValue([knownRun])
  vi.mocked(detectionApi.getDetectionModels).mockResolvedValue([])
  vi.mocked(topologyApi.getTopology).mockResolvedValue(snapshot)
  vi.mocked(topologyApi.getRunTopologyState).mockResolvedValue(runState)
})

describe('Digital Twin run-context persistence', () => {
  it('restores a known run from the URL after a simulated hard reload', async () => {
    renderApp(`/digital-twin?run=${knownRun.simulation_run_id}&seq=1`)
    await waitFor(() => {
      expect(topologyApi.getRunTopologyState).toHaveBeenCalledWith(
        knownRun.simulation_run_id,
        undefined,
        1,
      )
    })
    expect(await screen.findByText(/assets ·/)).toBeInTheDocument()
  })

  it('visibly represents the restored run and sequence instead of "run none"', async () => {
    const { container } = renderApp(`/digital-twin?run=${knownRun.simulation_run_id}&seq=4`)
    await waitFor(() => {
      expect(topologyApi.getRunTopologyState).toHaveBeenCalledWith(
        knownRun.simulation_run_id,
        undefined,
        4,
      )
    })
    const status = await screen.findByText(/· run /, { selector: 'p' })
    // The restored run id (first 8 chars, matching how a live run id is
    // rendered elsewhere on this page) and the restored sequence must be
    // visible - this is the user-observable fix, not just the API call.
    expect(status.textContent).toContain(knownRun.simulation_run_id.slice(0, 8))
    expect(status.textContent).toContain('seq 4')
    expect(status.textContent).not.toContain('run none')
    // The header chip must also stop claiming "Static topology" once a run
    // has been restored.
    expect(container.textContent).toContain('Restored replay')
    expect(container.textContent).not.toContain('Static topology')
  })

  it('drops an unknown/stale run id from the URL instead of crashing', async () => {
    renderApp('/digital-twin?run=does-not-exist&seq=4')
    await waitFor(() => {
      expect(new URLSearchParams(window.location.search).get('run')).toBeNull()
    })
    expect(topologyApi.getRunTopologyState).not.toHaveBeenCalled()
    expect(await screen.findByText(/assets ·/)).toBeInTheDocument()
    // Once cleared, the status line must honestly show no run - not the
    // discarded id and not a stale sequence.
    const status = await screen.findByText(/· run /, { selector: 'p' })
    expect(status.textContent).toContain('run none')
  })

  it('has no run context in the URL on a plain visit', async () => {
    renderApp('/digital-twin')
    expect(await screen.findByText(/assets ·/)).toBeInTheDocument()
    expect(new URLSearchParams(window.location.search).get('run')).toBeNull()
    expect(topologyApi.getRunTopologyState).not.toHaveBeenCalled()
  })
})
