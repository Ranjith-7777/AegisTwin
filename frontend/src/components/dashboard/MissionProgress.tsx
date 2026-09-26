import { Check } from 'lucide-react'

export type StageKey = 'simulate' | 'detect' | 'predict' | 'defend' | 'recover'

const STAGES: Array<{ key: StageKey; label: string }> = [
  { key: 'simulate', label: 'Simulate' },
  { key: 'detect', label: 'Detect' },
  { key: 'predict', label: 'Predict' },
  { key: 'defend', label: 'Defend' },
  { key: 'recover', label: 'Recover' },
]

/** Compact replacement for the long demonstration checklist. */
export function MissionProgress({ completed }: { completed: Record<StageKey, boolean> }) {
  const activeIndex = STAGES.findIndex((stage) => !completed[stage.key])
  return (
    <ol className="mission-progress" aria-label="Demonstration progress">
      {STAGES.map((stage, index) => {
        const done = completed[stage.key]
        const current = index === activeIndex
        return (
          <li
            key={stage.key}
            className={`mission-step${done ? ' is-done' : ''}${current ? ' is-current' : ''}`}
          >
            <span className="mission-marker" aria-hidden="true">
              {done ? <Check className="size-3" /> : index + 1}
            </span>
            {stage.label}
            <span className="sr-only">
              {done ? ' complete' : current ? ' in progress' : ' pending'}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
