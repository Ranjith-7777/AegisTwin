import { WS_BASE_URL } from '../lib/constants'
import { parseConnectionAck, type WebSocketConnectionState } from '../types/websocket'

export interface WebSocketClientHandlers {
  onStateChange?: (state: WebSocketConnectionState) => void
  onAcknowledgement?: (connectionId: string) => void
}

export class AegisTwinWebSocketClient {
  private socket: WebSocket | null = null

  constructor(private readonly handlers: WebSocketClientHandlers = {}) {}

  connect(): void {
    if (this.socket && this.socket.readyState < WebSocket.CLOSING) return
    this.handlers.onStateChange?.('connecting')
    this.socket = new WebSocket(`${WS_BASE_URL}/ws/events`)
    this.socket.addEventListener('open', () => this.handlers.onStateChange?.('connected'))
    this.socket.addEventListener('close', () => {
      this.socket = null
      this.handlers.onStateChange?.('disconnected')
    })
    this.socket.addEventListener('message', (event: MessageEvent<string>) => {
      try {
        const acknowledgement = parseConnectionAck(JSON.parse(event.data) as unknown)
        if (acknowledgement) {
          this.handlers.onAcknowledgement?.(acknowledgement.payload.connection_id)
        }
      } catch {
        // Malformed server messages are ignored; they never affect page rendering.
      }
    })
  }

  ping(): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type: 'ping' }))
    }
  }

  disconnect(): void {
    this.socket?.close(1000, 'Client disconnect')
    this.socket = null
    this.handlers.onStateChange?.('disconnected')
  }
}
