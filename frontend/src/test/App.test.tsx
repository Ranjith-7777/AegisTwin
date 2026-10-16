import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderApp } from './test-utils'
import { appRoutes } from '../lib/routes'
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
  it('renders the application', async () => {
    renderApp()
    expect(await screen.findByLabelText('Cloud Digital Twin')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Command Centre' })).toBeInTheDocument()
  })
  it('keeps the sidebar to ten lifecycle-ordered sections', async () => {
    renderApp()
    const nav = await screen.findByRole('navigation', { name: 'Primary navigation' })
    const expected = [
      'Command Centre',
      'Digital Twin',
      'Workflow & Agents',
      'Red Agent',
      'Incidents',
      'Threat Intelligence',
      'Reports',
      'Detection Models',
      'Audit Trail',
      'Settings',
    ]
    for (const label of expected)
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument()
    expect(within(nav).getAllByRole('link')).toHaveLength(expected.length)
    expect(await screen.findByText('Backend connected')).toBeInTheDocument()
  })
  it('keeps every original route reachable from navigation or sub-navigation', async () => {
    const original = [
      '/app',
      '/digital-twin',
      '/red-agent',
      '/telemetry',
      '/incidents',
      '/mitre',
      '/predictive-analytics',
      '/blue-agent/overview',
      '/blue-agent/agent-workflow',
      '/blue-agent/response-plans',
      '/blue-agent/policies',
      '/blue-agent/verification',
      '/evaluation',
      '/evaluation/experiments',
      '/evaluation/compare',
      '/evaluation/aggregate',
      '/evaluation/batches',
      '/model-analytics',
      '/audit-trail',
      '/settings',
    ]
    const reachable = new Set(appRoutes.map((route) => route.path))
    for (const path of original) expect(reachable.has(path)).toBe(true)
    renderApp('/mitre')
    const nav = await screen.findByRole('navigation', { name: 'Threat Intelligence sections' })
    for (const label of ['MITRE ATT&CK', 'Attack Prediction'])
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument()
  })
  it('renders safe system information without local environment values', async () => {
    renderApp('/settings')
    expect(await screen.findByRole('heading', { name: 'System Information' })).toBeInTheDocument()
    expect(await screen.findByText('0.8.0')).toBeInTheDocument()
    expect(await screen.findByText('20260722_0008')).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent('C:\\Users')
  })
  it('shows a compact simulation-only badge instead of a banner', async () => {
    renderApp()
    expect(await screen.findByRole('status', { name: 'Simulation-only safety' })).toHaveTextContent(
      'Simulation only',
    )
  })
  it('renders connected health status from the backend', async () => {
    renderApp()
    expect(await screen.findByText('Backend connected')).toBeInTheDocument()
    expect(
      await screen.findByRole('status', { name: /^Backend healthy, environment test$/ }),
    ).toBeInTheDocument()
    // The environment pill comes from the health response, not a hardcoded label.
    expect(await screen.findByText('Test')).toBeInTheDocument()
  })
  it('renders an unavailable state on backend failure', async () => {
    vi.mocked(systemApi.getHealth).mockRejectedValue(new Error('offline'))
    renderApp()
    expect((await screen.findAllByText('Backend unavailable')).length).toBeGreaterThan(0)
  })
  it('exposes the backend safety statement in the badge tooltip', async () => {
    renderApp()
    await waitFor(() => {
      expect(
        screen
          .getAllByRole('tooltip')
          .some((item) => item.textContent.includes('Backend confirms synthetic telemetry only.')),
      ).toBe(true)
    })
  })
  it('falls back to safe wording when safety is unavailable', async () => {
    vi.mocked(systemApi.getSafetyStatus).mockRejectedValue(new Error('offline'))
    renderApp()
    await waitFor(() => {
      expect(
        screen
          .getAllByRole('tooltip')
          .some((item) => item.textContent.includes('No action affects real systems')),
      ).toBe(true)
    })
  })
  it('renders the four command centre indicators without fabricated values', async () => {
    renderApp()
    const indicators = await screen.findByRole('group', { name: 'Key indicators' })
    expect(indicators.children).toHaveLength(4)
    for (const label of [
      'Digital Twin Assets',
      'Active Incidents',
      'Anomalies Detected',
      'Mitigations Executed',
    ])
      expect(within(indicators).getByText(label)).toBeInTheDocument()
  })
  it('renders the command centre workspace: twin, workflow rail, incident and decision', async () => {
    renderApp()
    expect(await screen.findByLabelText('Cloud Digital Twin')).toBeInTheDocument()
    const rail = await screen.findByRole('list', { name: 'Autonomous workflow progress' })
    expect(within(rail).getAllByRole('button')).toHaveLength(8)
    expect(screen.getByLabelText('Red Agent activity')).toBeInTheDocument()
    expect(screen.queryByLabelText('Threat activity')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Recent incidents')).toBeInTheDocument()
    expect(screen.getByLabelText('Blue Agent decision')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Launch simulation/ })).toHaveAttribute(
      'href',
      '/red-agent',
    )
    expect(screen.getByText('Standby')).toBeInTheDocument()
  })
  it('navigates to the interactive synthetic topology route', async () => {
    renderApp()
    await userEvent.click(await screen.findByRole('link', { name: 'Digital Twin' }))
    expect(
      await screen.findByRole('heading', { name: 'Cloud Digital Twin' }, { timeout: 5000 }),
    ).toBeInTheDocument()
    expect(screen.getByText(/sequence-bounded path evidence/)).toBeInTheDocument()
  })
  it('renders the 404 page for an unknown route', async () => {
    renderApp('/unknown')
    expect(await screen.findByRole('heading', { name: 'Route not found' })).toBeInTheDocument()
  })
  it('keeps the Blue workflow unavailable until a correlated incident exists', async () => {
    renderApp()
    await screen.findByRole('heading', { name: 'Command Centre' })
    expect(screen.queryByRole('button', { name: /Run Blue workflow/ })).not.toBeInTheDocument()
    expect(screen.getByText(/Waiting for a correlated incident/)).toBeInTheDocument()
  })
  it('does not display prohibited live-action claims', async () => {
    renderApp()
    await screen.findByRole('heading', { name: 'Command Centre' })
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
