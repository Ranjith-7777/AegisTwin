import { STATUS_LABEL, type StageId, type WorkflowStage } from '../../lib/workflowStages'
import { cn } from '../../lib/utils'
import { StageIcon } from './StageIcon'

/** The full 14-stage lifecycle as a vertical, selectable timeline. */
export function StageList({
  stages,
  selected,
  onSelect,
}: {
  stages: WorkflowStage[]
  selected: StageId | null
  onSelect: (id: StageId) => void
}) {
  return (
    <ol className="stage-list" aria-label="AegisArena lifecycle stages">
      {stages.map((stage) => (
        <li key={stage.id} className="contents">
          <button
            type="button"
            className={cn(
              'stage-row w-full',
              `st-${stage.status}`,
              selected === stage.id && 'is-selected',
            )}
            aria-current={selected === stage.id ? 'step' : undefined}
            onClick={() => {
              onSelect(stage.id)
            }}
          >
            <StageIcon status={stage.status} />
            <span className="min-w-0">
              <span className="stage-title">
                <span className="stage-index">{String(stage.index).padStart(2, '0')}</span>
                {stage.name}
              </span>
              <span className="stage-detail block">{stage.detail}</span>
            </span>
            <span className="stage-status-label">{STATUS_LABEL[stage.status]}</span>
          </button>
        </li>
      ))}
    </ol>
  )
}
