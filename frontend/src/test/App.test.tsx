import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderApp } from './test-utils'
import * as simulationApi from '../services/simulationApi'
import * as systemApi from '../services/systemApi'
import { parseConnectionAck } from '../types/websocket'

vi.mock('../services/systemApi')
vi.mock('../services/simulationApi')

const health = {
  status: 'healthy',
  service: 'AegisArena API',
  environment: 'test',
  simulation_only: true,
  database: 'connected',
} as const
const system = {
  system_name: 'AegisArena',
  system_tagline: 'Cloud Cyber Defense Range',
  mode: 'simulation',
  operational: true,
  active_incidents: 2,
  agents_online: 8,
  red_agent_runs: 0,
  blue_agent_orchestrations: 0,
  version: '0.8.0',
  git_commit: 'abcdef1',
  build_mode: 'production',
  demo_mode: true,
  database_revision: '20260722_0008',
  synthetic_only: true,
  benchmark_report_timestamp: '2026-07-22T00:00:00Z',
} as const
const safety = {
  simulation_only: true,
  real_world_actions_enabled: false,
  external_targets_allowed: false,
  message: 'Backend confirms synthetic telemetry only.',
} as const

beforeEach(() => {
  vi.mocked(systemApi.getHealth).mockResolvedValue(health)
  vi.mocked(systemApi.getSystemStatus).mockResolvedValue(system)
  vi.mocked(systemApi.getSafetyStatus).mockResolvedValue(safety)
  vi.mocked(simulationApi.getScenarios).mockResolvedValue([])
  vi.mocked(simulationApi.getSimulationRuns).mockResolvedValue([])
})

describe('AegisArena command centre', () => {
  it('renders the application', () => {
    renderApp()
    expect(screen.getByLabelText('Cloud Digital Twin')).toBeInTheDocument()
    expect(screen.getByLabelText('Demonstration progress')).toBeInTheDocument()
  })
  it('renders the five grouped sidebar entries', async () => {
    renderApp()
    const nav = screen.getByRole('navigation', { name: 'Primary navigation' })
    for (const label of ['Overview', 'Digital Twin', 'Threat Analysis', 'Defense', 'Results'])
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument()
    expect(within(nav).getAllByRole('link')).toHaveLength(5)
    expect(await screen.findByText('Backend connected')).toBeInTheDocument()
  })
  it('exposes every original route through section sub-navigation', async () => {
    renderApp('/telemetry')
    const nav = await screen.findByRole('navigation', { name: 'Threat Analysis sections' })
    for (const label of ['Live Telemetry', 'Incidents', 'MITRE ATT&CK', 'Attack Prediction'])
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument()
  })
  it('renders safe system information without local environment values', async () => {
    renderApp('/settings')
    expect(await screen.findByRole('heading', { name: 'System Information' })).toBeInTheDocument()
    expect(screen.getByText('0.8.0')).toBeInTheDocument()
    expect(screen.getByText('20260722_0008')).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent('C:\\Users')
  })
  it('shows a compact synthetic environment badge instead of a banner', () => {
    renderApp()
    expect(
      screen.getByRole('status', { name: 'Simulation environment safety notice' }),
    ).toHaveTextContent('Synthetic Environment')
    expect(screen.getByText('Simulation Mode')).toBeInTheDocument()
  })
  it('renders connected health status', async () => {
    renderApp()
    expect(await screen.findByText('Backend connected')).toBeInTheDocument()
    expect(await screen.findByText('System operational')).toBeInTheDocument()
  })
  it('renders disconnected state on backend failure', async () => {
    vi.mocked(systemApi.getHealth).mockRejectedValue(new Error('offline'))
    renderApp()
    expect(await screen.findByText('Backend disconnected')).toBeInTheDocument()
  })
  it('exposes the backend safety statement on the badge', async () => {
    renderApp()
    await waitFor(() => {
      expect(
        screen.getByRole('status', { name: 'Simulation environment safety notice' }),
      ).toHaveAttribute('title', 'Backend confirms synthetic telemetry only.')
    })
  })
  it('falls back to safe wording when safety is unavailable', async () => {
    vi.mocked(systemApi.getSafetyStatus).mockRejectedValue(new Error('offline'))
    renderApp()
    await waitFor(() => {
      expect(
        screen.getByRole('status', { name: 'Simulation environment safety notice' }),
      ).toHaveAttribute('title', expect.stringContaining('No action affects real systems'))
    })
  })
  it('renders exactly the four command centre KPI cards', () => {
    renderApp()
    for (const label of ['Cloud Health', 'Risk Score', 'Availability', 'Active Incidents'])
      expect(screen.getByLabelText(label)).toBeInTheDocument()
    expect(screen.getByLabelText('Cloud posture').children).toHaveLength(4)
  })
  it('renders the compact command centre workspace', () => {
    renderApp()
    expect(screen.getByLabelText('Cloud Digital Twin')).toBeInTheDocument()
    expect(screen.getByLabelText('Red Agent controls')).toBeInTheDocument()
    expect(screen.getByLabelText('Blue Agent recommendation')).toBeInTheDocument()
    // The long demonstration checklist is replaced by a five-step indicator.
    const steps = within(screen.getByLabelText('Demonstration progress')).getAllByRole('listitem')
    expect(steps).toHaveLength(5)
    expect(screen.getByLabelText('Demonstration progress')).toHaveTextContent(
      /Simulate.*Detect.*Predict.*Defend.*Recover/,
    )
  })
  it('navigates to the interactive synthetic topology route', async () => {
    renderApp()
    await userEvent.click(screen.getByRole('link', { name: 'Digital Twin' }))
    expect(
      await screen.findByRole('heading', { name: 'Cloud Digital Twin' }, { timeout: 5000 }),
    ).toBeInTheDocument()
    expect(screen.getByText(/sequence-bounded path evidence/)).toBeInTheDocument()
  })
  it('renders the 404 page for an unknown route', () => {
    renderApp('/unknown')
    expect(screen.getByRole('heading', { name: 'Route not found' })).toBeInTheDocument()
  })
  it('keeps Blue Agent ranking disabled until a run and model exist', () => {
    renderApp()
    expect(screen.getByRole('button', { name: 'Rank mitigations' })).toBeDisabled()
  })
  it('does not display prohibited live-action claims', () => {
    renderApp()
    expect(screen.queryByText(/isolate real endpoint/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/disable real account/i)).not.toBeInTheDocument()
  })
  it('parses WebSocket acknowledgements safely', () => {
    expect(
      parseConnectionAck({
        type: 'connection.ack',
        payload: { connection_id: 'abc', connected: true, simulation_only: true },
      })?.payload.connection_id,
    ).toBe('abc')
    expect(parseConnectionAck({ type: 'connection.ack', payload: { connected: true } })).toBeNull()
    expect(parseConnectionAck('invalid')).toBeNull()
  })
})
