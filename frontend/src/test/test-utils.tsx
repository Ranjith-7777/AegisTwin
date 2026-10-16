import { render, type RenderResult } from '@testing-library/react'
import { vi } from 'vitest'

import { App } from '../app/App'
import * as sessionApi from '../services/sessionApi'

export function renderApp(path = '/app'): RenderResult {
  if (!vi.isMockFunction(sessionApi.getSession)) {
    vi.spyOn(sessionApi, 'getSession').mockResolvedValue({
      role: 'ADMIN',
      authenticated: true,
      auth_mode: 'development_bypass',
      environment: 'test',
      can_operate: true,
      can_administer: true,
    })
  }
  window.history.pushState({}, '', path)
  return render(<App />)
}
