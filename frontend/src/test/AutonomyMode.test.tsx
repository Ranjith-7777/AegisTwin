import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderApp } from './test-utils'
import * as autonomyApi from '../services/autonomyApi'
import * as sessionApi from '../services/sessionApi'
import * as simulationApi from '../services/simulationApi'
import * as orchestrationApi from '../services/orchestrationApi'
import type { SessionView } from '../types/session'

vi.mock('../services/autonomyApi')
vi.mock('../services/sessionApi')
vi.mock('../services/simulationApi')
vi.mock('../services/orchestrationApi')

const config = {
  mode: 'recommend' as const,
  description: 'Generate and rank candidate plans but never execute automatically.',
  updated_by: 'system-default',
  updated_at: '2026-07-22T00:00:00Z',
  synthetic: true as const,
}

function session(role: SessionView['role']): SessionView {
  return {
    role,
    authenticated: true,
    auth_mode: role === 'VIEWER' ? 'easy_auth' : 'development_bypass',
    environment: 'development',
    can_operate: role !== 'VIEWER',
    can_administer: role === 'ADMIN',
  }
}

beforeEach(() => {
  vi.mocked(simulationApi.getScenarios).mockResolvedValue([])
  vi.mocked(simulationApi.getSimulationRuns).mockResolvedValue([])
  vi.mocked(orchestrationApi.listOrchestrations).mockResolvedValue([])
  vi.mocked(autonomyApi.getAutonomyConfig).mockResolvedValue(config)
  vi.mocked(autonomyApi.setAutonomyMode).mockResolvedValue({ ...config, mode: 'autonomous' })
  vi.mocked(sessionApi.getSession).mockResolvedValue(session('ADMIN'))
})

/** The switch sits behind the lifecycle card's autonomy disclosure. */
async function openAutonomySettings() {
  await userEvent.click(await screen.findByRole('button', { name: /mode$/ }, { timeout: 4000 }))
}

describe('autonomy mode control', () => {
  it('keeps the autonomy switch behind an accessible disclosure', async () => {
    renderApp('/workflow')
    const toggle = await screen.findByRole('button', { name: /mode$/ }, { timeout: 4000 })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('radio', { name: /^Observe/ })).not.toBeInTheDocument()
    await userEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(await screen.findByRole('radio', { name: /^Observe/ })).toBeInTheDocument()
  })

  it('makes the current mode explicit', async () => {
    renderApp('/workflow')
    await openAutonomySettings()
    const option = await screen.findByRole('radio', { name: /^Recommend/ })
    await waitFor(() => {
      expect(option).toHaveAttribute('aria-checked', 'true')
    })
    expect(screen.getByText(/never orchestrated or executed/)).toBeInTheDocument()
  })

  it('requires explicit confirmation before raising autonomy to autonomous', async () => {
    const user = userEvent.setup()
    renderApp('/workflow')
    await openAutonomySettings()
    const autonomous = await screen.findByRole('radio', { name: /^Autonomous/ })
    await waitFor(() => {
      expect(autonomous).toBeEnabled()
    })
    await user.click(autonomous)
    expect(screen.getByRole('dialog', { name: 'Enable autonomous mode?' })).toBeInTheDocument()
    expect(autonomyApi.setAutonomyMode).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Enable autonomous mode' }))
    await waitFor(() => {
      expect(autonomyApi.setAutonomyMode).toHaveBeenCalledWith(
        'autonomous',
        'Demo Operator (synthetic)',
        true,
      )
    })
  })

  it('switches lower modes without a confirmation dialog', async () => {
    const user = userEvent.setup()
    renderApp('/workflow')
    await openAutonomySettings()
    const observe = await screen.findByRole('radio', { name: /^Observe/ })
    await waitFor(() => {
      expect(observe).toBeEnabled()
    })
    await user.click(observe)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(autonomyApi.setAutonomyMode).toHaveBeenCalledWith(
      'observe',
      'Demo Operator (synthetic)',
      false,
    )
  })

  it('disables mode changes for a read-only viewer', async () => {
    vi.mocked(sessionApi.getSession).mockResolvedValue(session('VIEWER'))
    renderApp('/workflow')
    await openAutonomySettings()
    const autonomous = await screen.findByRole('radio', { name: /^Autonomous/ })
    await waitFor(() => {
      expect(screen.getByLabelText('Role VIEWER')).toBeInTheDocument()
    })
    expect(autonomous).toBeDisabled()
  })
})
