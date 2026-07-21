import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderApp } from './test-utils'
import * as systemApi from '../services/systemApi'
import { parseConnectionAck } from '../types/websocket'

vi.mock('../services/systemApi')

const health = {
  status: 'healthy',
  service: 'AegisTwin API',
  environment: 'test',
  simulation_only: true,
  database: 'connected',
} as const
const system = {
  system_name: 'AegisTwin',
  mode: 'simulation',
  operational: true,
  active_incidents: 2,
  agents_online: 3,
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
})

describe('AegisTwin dashboard foundation', () => {
  it('renders the application', () => {
    renderApp()
    expect(screen.getByRole('heading', { name: 'Operational posture' })).toBeInTheDocument()
  })
  it('renders sidebar navigation', async () => {
    renderApp()
    expect(screen.getByRole('navigation', { name: 'Primary navigation' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Digital Twin' })).toBeInTheDocument()
    expect(await screen.findByText('Backend: Connected')).toBeInTheDocument()
  })
  it('renders the persistent simulation banner', () => {
    renderApp()
    expect(
      screen.getByRole('status', { name: 'Simulation environment safety notice' }),
    ).toHaveTextContent('SIMULATION ENVIRONMENT')
  })
  it('renders connected health status', async () => {
    renderApp()
    expect(await screen.findByText('Backend: Connected')).toBeInTheDocument()
  })
  it('renders disconnected state on backend failure', async () => {
    vi.mocked(systemApi.getHealth).mockRejectedValue(new Error('offline'))
    renderApp()
    expect(await screen.findByText('Backend: Disconnected')).toBeInTheDocument()
  })
  it('populates system values from the backend', async () => {
    renderApp()
    await waitFor(() => {
      expect(screen.getByLabelText('Active Incidents')).toHaveTextContent('2')
    })
    expect(screen.getByLabelText('Agents Online')).toHaveTextContent('3')
  })
  it('displays a valid backend safety response', async () => {
    renderApp()
    expect(await screen.findByText(/Backend confirms synthetic telemetry only/)).toBeInTheDocument()
  })
  it('falls back to safe banner wording when safety is unavailable', async () => {
    vi.mocked(systemApi.getSafetyStatus).mockRejectedValue(new Error('offline'))
    renderApp()
    expect(await screen.findByText(/No action affects real systems/)).toBeInTheDocument()
  })
  it('renders all five metric cards', () => {
    renderApp()
    for (const label of ['Active Incidents', 'Global Risk Score', 'MTTD', 'MTTR', 'Agents Online'])
      expect(screen.getByLabelText(label)).toBeInTheDocument()
  })
  it('renders dashboard placeholder panels', () => {
    renderApp()
    expect(screen.getByText('Cyber Digital Twin')).toBeInTheDocument()
    expect(screen.getByText('Live Event Stream')).toBeInTheDocument()
    expect(screen.getByText('MITRE ATT&CK Timeline')).toBeInTheDocument()
  })
  it('navigates to a polished placeholder route', async () => {
    renderApp()
    await userEvent.click(screen.getByRole('link', { name: 'Digital Twin' }))
    expect(screen.getByRole('heading', { name: 'Digital Twin' })).toBeInTheDocument()
    expect(screen.getByText(/intentionally deferred/)).toBeInTheDocument()
  })
  it('renders the 404 page for an unknown route', () => {
    renderApp('/unknown')
    expect(screen.getByRole('heading', { name: 'Route not found' })).toBeInTheDocument()
  })
  it('keeps response controls disabled', () => {
    renderApp()
    expect(screen.getByRole('button', { name: 'Response controls unavailable' })).toBeDisabled()
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
