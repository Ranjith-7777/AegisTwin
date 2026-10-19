import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../app/App'
import * as sessionApi from '../services/sessionApi'

vi.mock('../services/sessionApi')

const anonymous = {
  role: 'VIEWER' as const,
  authenticated: false,
  auth_mode: 'anonymous' as const,
  environment: 'test',
  can_operate: false,
  can_administer: false,
}

const development = {
  role: 'ADMIN' as const,
  authenticated: true,
  auth_mode: 'development_bypass' as const,
  environment: 'development',
  can_operate: true,
  can_administer: true,
}

beforeEach(() => {
  window.history.pushState({}, '', '/')
  vi.mocked(sessionApi.getSession).mockResolvedValue(anonymous)
})

describe('public landing and authentication experience', () => {
  it('renders the complete public hero without requesting authentication', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: /Simulate Threats/i })).toBeInTheDocument()
    expect(screen.getAllByLabelText('Simulated Digital Twin product demonstration')).toHaveLength(2)
    expect(screen.getByRole('heading', { name: /complete defense lifecycle/i })).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /attack signal to verified resilience/i }),
    ).toBeInTheDocument()
  })

  it('sends an anonymous launch request to the sign-in page with a safe destination', async () => {
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: /Launch AegisArena/i }))
    expect(
      await screen.findByRole('heading', { name: 'Welcome to AegisArena' }),
    ).toBeInTheDocument()
    expect(window.location.pathname).toBe('/login')
    expect(window.location.search).toBe('?next=%2Fapp')
  })

  it('uses Easy Auth and rejects an external post-login redirect', async () => {
    window.history.pushState({}, '', '/login?next=https://example.com')
    render(<App />)
    const signIn = await screen.findByRole('link', { name: /Sign in with Microsoft/i })
    await waitFor(() => {
      expect(signIn).toHaveAttribute('href', expect.stringContaining('%2Fapp'))
    })
    expect(signIn.getAttribute('href')).not.toContain('example.com')
  })

  it('redirects anonymous console access to login', async () => {
    window.history.pushState({}, '', '/app')
    render(<App />)
    expect(
      await screen.findByRole('heading', { name: 'Welcome to AegisArena' }),
    ).toBeInTheDocument()
    expect(window.location.search).toBe('?next=%2Fapp')
  })

  it('requires an explicit Development Mode entry before opening the local console', async () => {
    vi.mocked(sessionApi.getSession).mockResolvedValue(development)
    window.history.pushState({}, '', '/login?next=%2Fapp')
    render(<App />)

    const developmentMode = await screen.findByLabelText('Development Mode')
    expect(developmentMode).toHaveTextContent('Backend-verified admin access')
    expect(developmentMode).toHaveTextContent('Roles cannot be chosen here')
    expect(screen.queryByRole('radio')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Enter development console/i }))
    await waitFor(() => {
      expect(window.location.pathname).toBe('/app')
    })
    expect(await screen.findByRole('heading', { name: 'Command Centre' })).toBeInTheDocument()
  })

  it('rejects a development bypass session if a production response ever exposes one', async () => {
    vi.mocked(sessionApi.getSession).mockResolvedValue({
      ...development,
      environment: 'production',
    })
    window.history.pushState({}, '', '/app')
    render(<App />)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'An unsafe production development session was rejected.',
    )
    expect(window.location.pathname).toBe('/login')
    expect(screen.queryByLabelText('Development Mode')).not.toBeInTheDocument()
  })
})
