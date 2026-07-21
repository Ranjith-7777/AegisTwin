import { CircleAlert } from 'lucide-react'

import { Button } from '../ui/button'

interface ErrorStateProps {
  message: string
  correlationId?: string
  onRetry: () => void
}

export function ErrorState({ message, correlationId, onRetry }: ErrorStateProps) {
  return (
    <div
      className="flex flex-wrap items-center gap-3 rounded-lg border border-red-900/70 bg-red-950/30 p-4"
      role="alert"
    >
      <CircleAlert className="size-5 text-red-300" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-red-100">{message}</p>
        {correlationId ? (
          <p className="technical mt-1 text-xs text-red-300">Reference: {correlationId}</p>
        ) : null}
      </div>
      <Button variant="outline" size="sm" onClick={onRetry}>
        Retry connection
      </Button>
    </div>
  )
}
