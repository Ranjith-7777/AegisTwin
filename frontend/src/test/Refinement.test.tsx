import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderApp } from './test-utils'
import * as purpleTeamApi from '../services/purpleTeamApi'
import * as simulationApi from '../services/simulationApi'
import * as systemApi from '../services/systemApi'
import type { SimulationScenario } from '../types/simulation'

vi.mock('../services/systemApi')
vi.mock('../services/simulationApi')
vi.mock('../services/purpleTeamApi')

const scenario: SimulationScenario = {
  scenario_id: 'staged-compromise-demo',
  name: 'Staged Cloud Compromise Demonstration',
  description: 'A deterministic staged exercise.',
  synthetic: true,
  steps: [
    {
      sequence: 1,
      offset_seconds: 0,
      description: 'Normal sign-in',
      event_type: 'authentication',
      action: 'login',
      outcome: 'success',
      severity: 'low',
      source_type: 'user',
      source_id: 'external-user-01',
      destination_id: 'api-gateway-01',
    },
  ],
}

beforeEach(() => {
  window.localStorage.clear()
  vi.mocked(systemApi.getHealth).mockResolvedValue({
    status: 'healthy',
    service: 'AegisArena API',
    environment: 'test',
    simulation_only: true,
    database: 'connected',
  })
  vi.mocked(systemApi.getSafetyStatus).mockResolvedValue({
    simulation_only: true,
    real_world_actions_enabled: false,
    external_targets_allowed: false,
    message: 'Backend confirms synthetic telemetry only.',
  })
  vi.mocked(simulationApi.getScenarios).mockResolvedValue([scenario])
  vi.mocked(simulationApi.getSimulationRuns).mockResolvedValue([])
  vi.mocked(purpleTeamApi.listRedScenarios).mockResolvedValue([])
  vi.mocked(purpleTeamApi.getScenarioDefinition).mockRejectedValue(new Error('not needed'))
})

describe('sidebar icon rail', () => {
  it('collapses to an icon rail that keeps every link named and remembers the choice', async () => {
    const { unmount } = renderApp()
    const nav = await screen.findByRole('navigation', { name: 'Primary navigation' })
    const toggle = await screen.findByRole('button', { name: 'Collapse sidebar' })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await userEvent.click(toggle)
    expect(screen.getByRole('button', { name: 'Expand sidebar' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
    // Labels stay in the accessibility tree and drive the hover/focus tooltip.
    const link = within(nav).getByRole('link', { name: 'Digital Twin' })
    expect(link).toHaveAttribute('data-tip', 'Digital Twin')
    expect(window.localStorage.getItem('aegisarena.sidebarCollapsed')).toBe('true')
    unmount()
    renderApp()
    expect(await screen.findByRole('button', { name: 'Expand sidebar' })).toBeInTheDocument()
  })
})

describe('workflow sections', () => {
  it('shows one section at a time and starts with an actionable next step', async () => {
    renderApp('/workflow')
    const tabs = await screen.findByRole('tablist', { name: 'Workflow sections' })
    expect(within(tabs).getByRole('tab', { name: 'Overview' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    const next = screen.getByLabelText('Next step')
    expect(next).toHaveTextContent('Launch a scenario')
    expect(within(next).getByRole('link', { name: /Open Red Agent lab/ })).toHaveAttribute(
      'href',
      '/red-agent',
    )
    await userEvent.click(within(tabs).getByRole('tab', { name: 'Red Agent' }))
    expect(within(tabs).getByRole('tab', { name: 'Red Agent' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByLabelText('Red Agent scenario timeline')).toBeInTheDocument()
    expect(screen.queryByLabelText('Next step')).not.toBeInTheDocument()
  })
})

describe('Red Agent lab', () => {
  it('guides the run and keeps advanced settings behind a disclosure', async () => {
    renderApp('/red-agent')
    expect(await screen.findByRole('list', { name: 'Simulation steps' })).toHaveTextContent(
      'Choose a scenario',
    )
    expect(
      await screen.findByRole('radio', { name: /Staged Cloud Compromise Demonstration/ }),
    ).toHaveAttribute('aria-checked', 'true')
    const summary = screen.getByText('Advanced settings')
    const details = summary.closest('details')
    expect(details).not.toBeNull()
    expect(details?.open).toBe(false)
    await userEvent.click(summary)
    expect(details?.open).toBe(true)
    expect(screen.getByLabelText('Random seed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Launch scenario/ })).toBeInTheDocument()
  })
})
