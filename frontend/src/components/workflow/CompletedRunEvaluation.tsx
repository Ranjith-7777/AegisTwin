import { BarChart3 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { toClientApiError } from '../../services/apiClient'
import { evaluateCompletedWorkflow } from '../../services/evaluationApi'
import { Button } from '../ui/button'

const EVALUABLE_STATES = new Set([
  'verified',
  'synthetic_execution_failed',
  'synthetic_rollback_completed',
])

interface CompletedRunEvaluationProps {
  orchestrationId: string | null
  state: string | null
  canOperate: boolean
}

export function CompletedRunEvaluation({
  orchestrationId,
  state,
  canOperate,
}: CompletedRunEvaluationProps) {
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!orchestrationId || !state || !EVALUABLE_STATES.has(state)) return null

  function evaluate() {
    if (!orchestrationId) return
    setBusy(true)
    setError(null)
    void evaluateCompletedWorkflow(orchestrationId)
      .then((experiment) => {
        void navigate(`/evaluation/experiments/${experiment.experiment_id}/report`)
      })
      .catch((cause: unknown) => {
        setError(toClientApiError(cause).message)
      })
      .finally(() => {
        setBusy(false)
      })
  }

  return (
    <div>
      <Button
        variant="outline"
        disabled={!canOperate || busy}
        title={canOperate ? undefined : 'Requires ANALYST or ADMIN'}
        onClick={evaluate}
      >
        <BarChart3 /> {busy ? 'Evaluating…' : 'Evaluate completed run'}
      </Button>
      {error ? (
        <p role="alert" className="mt-2 text-xs text-red-700">
          {error}
        </p>
      ) : null}
    </div>
  )
}
