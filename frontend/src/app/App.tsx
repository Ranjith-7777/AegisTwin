import { BrowserRouter } from 'react-router-dom'

import { AppRoutes } from './router'
import { SystemDataProvider } from './providers'
import { SimulationPlaybackProvider } from './SimulationPlaybackProvider'

export function App() {
  return (
    <BrowserRouter>
      <SystemDataProvider>
        <SimulationPlaybackProvider>
          <AppRoutes />
        </SimulationPlaybackProvider>
      </SystemDataProvider>
    </BrowserRouter>
  )
}
