import { CheckCircle2, Circle } from 'lucide-react'

export interface ActivityItem {
  label: string
  detail: string
  done: boolean
}

/**
 * A compact "what has happened so far" list derived entirely from state this
 * page already holds — not a new timeline data source, and not the future
 * Phase 5 unified observability timeline.
 */
export function RecentActivity({ items }: { items: ActivityItem[] }) {
  return (
    <section className="card" aria-label="Recent activity">
      <div className="card-head">
        <h2 className="card-title">Recent Activity</h2>
      </div>
      <ul className="grid gap-3 p-4">
        {items.map((item) => (
          <li key={item.label} className="flex items-start gap-3">
            {item.done ? (
              <CheckCircle2
                className="mt-0.5 size-4 shrink-0 text-emerald-600"
                aria-hidden="true"
              />
            ) : (
              <Circle className="mt-0.5 size-4 shrink-0 text-slate-300" aria-hidden="true" />
            )}
            <div>
              <p className={item.done ? 'font-medium text-slate-900' : 'text-slate-500'}>
                {item.label}
              </p>
              <p className="text-xs text-slate-500">{item.detail}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
