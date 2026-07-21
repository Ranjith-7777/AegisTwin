import { BrowserRouter } from 'react-router-dom'

import { AppRoutes } from './router'
import { SystemDataProvider } from './providers'

export function App() {
  return (
    <BrowserRouter>
      <SystemDataProvider>
        <AppRoutes />
      </SystemDataProvider>
    </BrowserRouter>
  )
}
