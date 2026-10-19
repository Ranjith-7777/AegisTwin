import { STATUS_LABEL, type RailStep, type StageId } from '../../lib/workflowStages'
import { cn } from '../../lib/utils'
import { StageIcon } from '../workflow/StageIcon'

const REACHED = new Set(['completed', 'rolled_back', 'running', 'awaiting', 'warning'])

/**
 * Horizontal Red → Recover stepper. Each step aggregates the lifecycle stages
 * it covers; selecting one opens those stages' persisted evidence.
 */
export function IncidentStepper({
  steps,
  selected,
  onSelect,
}: {
  steps: RailStep[]
  selected: StageId | null
  onSelect: (id: StageId) => void
}) {
  return (
    <ol className="stepper" aria-label="Incident workflow steps">
      {steps.map((step) => (
        <li
          key={step.id}
          className={cn(
            REACHED.has(step.status) && 'is-reached',
            ['failed', 'blocked'].includes(step.status) && 'is-alert',
          )}
        >
          <button
            type="button"
            className={cn(
              'step',
              `st-${step.status}`,
              selected !== null && step.stageIds.includes(selected) && 'is-selected',
            )}
            aria-label={`${step.label}: ${STATUS_LABEL[step.status]}. ${step.detail}`}
            onClick={() => {
              onSelect(step.stageIds[0] ?? 'attack')
            }}
          >
            <span className="step-dot">
              <StageIcon status={step.status} />
            </span>
            <span className="step-name">{step.label}</span>
            <span className="step-state">{STATUS_LABEL[step.status]}</span>
            <span className="step-detail">{step.detail}</span>
          </button>
        </li>
      ))}
    </ol>
  )
}
