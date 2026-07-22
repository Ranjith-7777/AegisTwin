import { WS_BASE_URL } from '../lib/constants'
import { parsePlaybackEnvelope, type PlaybackEnvelope } from '../types/playback'
import type { WebSocketConnectionState } from '../types/websocket'

export type PlaybackControlType = 'start' | 'pause' | 'resume' | 'stop' | 'ping'
export interface DetectionControl {
  detectionEnabled: boolean
  modelId?: string
  correlationEnabled?: boolean
}

export interface PlaybackClientHandlers {
  onConnectionState: (state: WebSocketConnectionState) => void
  onMessage: (message: PlaybackEnvelope) => void
  onProtocolError: (message: string) => void
}

export class PlaybackWebSocketClient {
  private socket: WebSocket | null = null

  constructor(private readonly handlers: PlaybackClientHandlers) {}

  connect(runId: string, afterSequence = 0): boolean {
    if (this.socket && this.socket.readyState < WebSocket.CLOSING) return false
    this.handlers.onConnectionState('connecting')
    const url = `${WS_BASE_URL}/api/v1/ws/simulation/runs/${encodeURIComponent(runId)}?after_sequence=${String(afterSequence)}`
    this.socket = new WebSocket(url)
    this.socket.addEventListener('open', () => {
      this.handlers.onConnectionState('connected')
    })
    this.socket.addEventListener('error', () => {
      this.handlers.onConnectionState('error')
      this.handlers.onProtocolError('The synthetic playback connection failed.')
    })
    this.socket.addEventListener('close', () => {
      this.socket = null
      this.handlers.onConnectionState('disconnected')
    })
    this.socket.addEventListener('message', (event: MessageEvent<string>) => {
      try {
        const parsed = parsePlaybackEnvelope(JSON.parse(event.data) as unknown)
        if (!parsed) {
          this.handlers.onProtocolError('A malformed playback message was rejected.')
          return
        }
        this.handlers.onMessage(parsed)
      } catch {
        this.handlers.onProtocolError('A malformed playback message was rejected.')
      }
    })
    return true
  }

  sendControl(
    messageType: PlaybackControlType,
    afterSequence?: number,
    detection?: DetectionControl,
  ): boolean {
    if (this.socket?.readyState !== WebSocket.OPEN) return false
    this.socket.send(
      JSON.stringify({
        message_type: messageType,
        ...(afterSequence === undefined ? {} : { after_sequence: afterSequence }),
        ...(messageType === 'start' && detection?.detectionEnabled
          ? {
              detection_enabled: true,
              model_id: detection.modelId,
              ...(detection.correlationEnabled ? { correlation_enabled: true } : {}),
            }
          : {}),
      }),
    )
    return true
  }

  disconnect(): void {
    this.socket?.close(1000, 'Synthetic playback client disconnect')
    this.socket = null
    this.handlers.onConnectionState('disconnected')
  }
}
