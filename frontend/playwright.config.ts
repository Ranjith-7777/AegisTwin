import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const python =
  process.platform === 'win32'
    ? path.join(root, 'backend', '.venv', 'Scripts', 'python.exe')
    : 'python'

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:4307',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `"${python}" ../scripts/start_e2e_backend.py`,
      cwd: path.join(root, 'frontend'),
      url: 'http://127.0.0.1:8010/api/health',
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 4307',
      cwd: path.join(root, 'frontend'),
      url: 'http://127.0.0.1:4307',
      env: {
        ...process.env,
        VITE_API_BASE_URL: 'http://127.0.0.1:8010',
        VITE_WS_BASE_URL: 'ws://127.0.0.1:8010',
        VITE_DEMO_MODE: 'true',
      },
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
})
