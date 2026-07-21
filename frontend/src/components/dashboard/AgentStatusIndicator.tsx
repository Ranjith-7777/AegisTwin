import { Bot } from 'lucide-react'

export function AgentStatusIndicator({ count, live }: { count: number; live: boolean }) {
  return (
    <span className="status-chip" aria-label={`${String(count)} agents online`}>
      <Bot className="size-3.5" aria-hidden="true" />
      {live ? `${String(count)} Online` : 'Unavailable'}
    </span>
  )
}
