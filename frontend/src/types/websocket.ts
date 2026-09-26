export type WebSocketConnectionState =
  'idle' | 'connecting' | 'connected' | 'disconnected' | 'error'

export interface ConnectionAckMessage {
  type: 'connection.ack'
  payload: {
    connection_id: string
    connected: true
    simulation_only: true
  }
}

export interface PongMessage {
  type: 'pong'
  payload: { simulation_only: true }
}

export type ServerWebSocketMessage = ConnectionAckMessage | PongMessage

export function parseConnectionAck(value: unknown): ConnectionAckMessage | null {
  if (typeof value !== 'object' || value === null) return null
  const candidate = value as Record<string, unknown>
  if (candidate.type !== 'connection.ack') return null
  const payload = candidate.payload
  if (typeof payload !== 'object' || payload === null) return null
  const fields = payload as Record<string, unknown>
  if (
    typeof fields.connection_id !== 'string' ||
    fields.connection_id.length === 0 ||
    fields.connected !== true ||
    fields.simulation_only !== true
  ) {
    return null
  }
  return {
    type: 'connection.ack',
    payload: {
      connection_id: fields.connection_id,
      connected: true,
      simulation_only: true,
    },
  }
}
