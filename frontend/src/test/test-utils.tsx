import { render, type RenderResult } from '@testing-library/react'

import { App } from '../app/App'

export function renderApp(path = '/'): RenderResult {
  window.history.pushState({}, '', path)
  return render(<App />)
}
