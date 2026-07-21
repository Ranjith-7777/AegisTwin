import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { renderApp } from './test-utils'
import * as simulationApi from '../services/simulationApi'
import * as systemApi from '../services/systemApi'
import type { PlaybackEnvelope } from '../types/playback'
import type { SimulationRun, SimulationScenario, TelemetryEvent } from '../types/simulation'

vi.mock('../services/simulationApi')
vi.mock('../services/systemApi')

class FakeWebSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3
  static instances: FakeWebSocket[] = []

  readonly url: string
  readyState = FakeWebSocket.CONNECTING
  sent: string[] = []
  closeCalled = false
  private listeners = new Map<string, Array<(event: Event | MessageEvent<string>) => void>>()

  constructor(url: string | URL) {
    this.url = String(url)
    FakeWebSocket.instances.push(this)
  }

  addEventListener(type: string, listener: (event: Event | MessageEvent<string>) => void) {
    const listeners = this.listeners.get(type) ?? []
    listeners.push(listener)
    this.listeners.set(type, listeners)
  }

  send(message: string) {
    this.sent.push(message)
  }

  close() {
    this.closeCalled = true
    this.readyState = FakeWebSocket.CLOSED
    this.dispatch('close', new Event('close'))
  }

  open() {
    this.readyState = FakeWebSocket.OPEN
    this.dispatch('open', new Event('open'))
  }

  emit(message: PlaybackEnvelope | string) {
    const data = typeof message === 'string' ? message : JSON.stringify(message)
    this.dispatch('message', { data } as MessageEvent<string>)
  }

  fail() {
    this.dispatch('error', new Event('error'))
  }

  private dispatch(type: string, event: Event | MessageEvent<string>) {
    for (const listener of this.listeners.get(type) ?? []) listener(event)
  }
}

const scenario: SimulationScenario = {
  scenario_id: 'scenario-1',
  name: 'Synthetic Access Exercise',
  description: 'A deterministic exercise.',
  synthetic: true,
  steps: [],
}

const run: SimulationRun = {
  simulation_run_id: 'run-12345678',
  scenario_id: scenario.scenario_id,
  seed: 42,
  start_time: '2026-07-21T09:00:00Z',
  playback_speed: 10,
  status: 'completed',
  event_count: 2,
  created_at: '2026-07-21T08:59:00Z',
}

const telemetryEvent: TelemetryEvent = {
  event_id: 'event-1',
  scenario_id: scenario.scenario_id,
  simulation_run_id: run.simulation_run_id,
  timestamp: '2026-07-21T09:00:05Z',
  event_type: 'authentication',
  action: 'login_attempt',
  outcome: 'failure',
  severity: 'medium',
  source_type: 'user',
  source_id: 'synthetic-user-1',
  destination_id: 'synthetic-service-1',
  user_id: 'exercise-user',
  device_id: null,
  source_ip: null,
  destination_ip: null,
  privilege_level: null,
  failed_attempts: 1,
  bytes_transferred: 0,
  process_name: null,
  metadata: { synthetic: true },
  created_at: '2026-07-21T08:59:00Z',
}

function envelope(
  messageType: PlaybackEnvelope['message_type'],
  payload: Record<string, unknown> = {},
  sequenceNumber = 1,
): PlaybackEnvelope {
  return {
    message_type: messageType,
    run_id: run.simulation_run_id,
    sequence_number: sequenceNumber,
    server_timestamp: '2026-07-21T09:00:00Z',
    synthetic: true,
    payload,
  }
}

async function startRun() {
  renderApp()
  await screen.findByRole('option', { name: scenario.name })
  await userEvent.click(screen.getByRole('button', { name: 'Start Synthetic Simulation' }))
  await waitFor(() => {
    expect(simulationApi.createSimulationRun).toHaveBeenCalledOnce()
  })
  const socket = FakeWebSocket.instances.at(-1)
  if (!socket) throw new Error('Expected playback socket to be created.')
  return socket
}

function sentControlTypes(socket: FakeWebSocket): unknown[] {
  return socket.sent.map((value) => {
    const parsed: unknown = JSON.parse(value)
    if (typeof parsed !== 'object' || parsed === null || !('message_type' in parsed)) return null
    return parsed.message_type
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  FakeWebSocket.instances = []
  vi.stubGlobal('WebSocket', FakeWebSocket)
  vi.mocked(simulationApi.getScenarios).mockResolvedValue([scenario])
  vi.mocked(simulationApi.getSimulationRuns).mockResolvedValue([])
  vi.mocked(simulationApi.createSimulationRun).mockResolvedValue(run)
  vi.mocked(systemApi.getHealth).mockResolvedValue({
    status: 'healthy',
    service: 'AegisTwin API',
    environment: 'test',
    simulation_only: true,
    database: 'connected',
  })
  vi.mocked(systemApi.getSystemStatus).mockResolvedValue({
    system_name: 'AegisTwin',
    mode: 'simulation',
    operational: true,
    active_incidents: 0,
    agents_online: 0,
  })
  vi.mocked(systemApi.getSafetyStatus).mockResolvedValue({
    simulation_only: true,
    real_world_actions_enabled: false,
    external_targets_allowed: false,
    message: 'Synthetic only.',
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('synthetic playback dashboard', () => {
  it('stays disconnected until the user explicitly starts a run', async () => {
    renderApp()
    expect(await screen.findByRole('option', { name: scenario.name })).toBeInTheDocument()
    expect(FakeWebSocket.instances).toHaveLength(0)
    expect(screen.getByText('disconnected')).toBeInTheDocument()
  })

  it('creates a run, connects to its versioned endpoint, and starts after acknowledgement', async () => {
    const socket = await startRun()
    expect(socket.url).toContain('/api/v1/ws/simulation/runs/run-12345678?after_sequence=0')
    act(() => {
      socket.open()
    })
    act(() => {
      socket.emit(envelope('connection_ack'))
    })
    expect(sentControlTypes(socket)).toContain('start')
  })

  it('renders telemetry incrementally with factual synthetic labels', async () => {
    const socket = await startRun()
    act(() => {
      socket.open()
    })
    act(() => {
      socket.emit(envelope('connection_ack'))
    })
    act(() => {
      socket.emit(
        envelope(
          'telemetry_event',
          { event_index: 1, total_event_count: 2, event: telemetryEvent },
          3,
        ),
      )
    })
    expect(await screen.findByText('login_attempt')).toBeInTheDocument()
    expect(screen.getByText('1 / 2')).toBeInTheDocument()
    expect(screen.getAllByText('Synthetic').length).toBeGreaterThan(0)
    expect(screen.getByText(/not a confirmed attack/i)).toBeInTheDocument()
  })

  it('sends pause, resume, and stop controls and reflects server state', async () => {
    const socket = await startRun()
    act(() => {
      socket.open()
    })
    act(() => {
      socket.emit(envelope('connection_ack'))
    })
    act(() => {
      socket.emit(envelope('playback_started', {}, 2))
    })
    await userEvent.click(screen.getByRole('button', { name: 'Pause' }))
    act(() => {
      socket.emit(envelope('playback_paused', {}, 3))
    })
    await userEvent.click(screen.getByRole('button', { name: 'Resume' }))
    act(() => {
      socket.emit(envelope('playback_resumed', {}, 4))
    })
    await userEvent.click(screen.getByRole('button', { name: 'Stop' }))
    act(() => {
      socket.emit(envelope('playback_stopped', {}, 5))
    })
    const controls = sentControlTypes(socket)
    expect(controls).toEqual(['start', 'pause', 'resume', 'stop'])
    expect(screen.getByText('stopped')).toBeInTheDocument()
    expect(socket.closeCalled).toBe(true)
  })

  it('rejects malformed messages and offers retry after a connection error', async () => {
    const socket = await startRun()
    act(() => {
      socket.open()
    })
    act(() => {
      socket.emit('{not-json')
    })
    expect(await screen.findAllByText(/malformed playback message/i)).not.toHaveLength(0)
    act(() => {
      socket.fail()
    })
    await userEvent.click(await screen.findByRole('button', { name: 'Retry connection' }))
    expect(FakeWebSocket.instances).toHaveLength(2)
    const retrySocket = FakeWebSocket.instances[1]
    if (!retrySocket) throw new Error('Expected retry socket to be created.')
    expect(retrySocket.url).toContain('after_sequence=0')
  })

  it('closes an active socket during component cleanup', async () => {
    const { unmount } = renderApp()
    await screen.findByRole('option', { name: scenario.name })
    await userEvent.click(screen.getByRole('button', { name: 'Start Synthetic Simulation' }))
    const socket = FakeWebSocket.instances[0]
    if (!socket) throw new Error('Expected playback socket to be created.')
    unmount()
    expect(socket.closeCalled).toBe(true)
  })

  it('does not fabricate anomaly, incident, MTTD, or MTTR values', () => {
    renderApp()
    expect(screen.queryByText(/anomaly score/i)).not.toBeInTheDocument()
    expect(screen.getByLabelText('MTTD')).toHaveTextContent('--')
    expect(screen.getByLabelText('MTTR')).toHaveTextContent('--')
  })
})
