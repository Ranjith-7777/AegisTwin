import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Gauge } from 'lucide-react'

import { getExperimentMetrics, listExperiments } from '../../services/evaluationApi'

function mean(values: number[]): number | null {
  if (values.length === 0) return null
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

/**
 * Command Centre's resilience summary: the mean Aegis Resilience Score and
 * Mission Continuity Index across completed, persisted evaluation
 * experiments — the same source data as the Evaluation Overview page, never
 * a live/estimated figure. Empty until at least one experiment has run.
 */
export function ResilienceCard() {
  const [meanArs, setMeanArs] = useState<number | null>(null)
  const [meanMci, setMeanMci] = useState<number | null>(null)
  const [experimentCount, setExperimentCount] = useState(0)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    void listExperiments()
      .then((experiments) => {
        const completedIds = experiments
          .filter((item) => item.status === 'completed')
          .map((item) => item.experiment_id)
        return Promise.all(completedIds.map((id) => getExperimentMetrics(id).catch(() => null)))
      })
      .then((metricsRows) => {
        if (cancelled) return
        const arsValues = metricsRows
          .map((metrics) => metrics?.ars_total)
          .filter((value): value is number => typeof value === 'number')
        const mciValues = metricsRows
          .map((metrics) => metrics?.mci)
          .filter((value): value is number => typeof value === 'number')
        setMeanArs(mean(arsValues))
        setMeanMci(mean(mciValues))
        setExperimentCount(arsValues.length)
      })
      .catch(() => {
        if (!cancelled) {
          setMeanArs(null)
          setMeanMci(null)
          setExperimentCount(0)
        }
      })
      .finally(() => {
        if (!cancelled) setLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="card" aria-label="Resilience">
      <div className="card-head">
        <h2 className="card-title">
          <Gauge className="size-4 shrink-0" aria-hidden="true" />
          Resilience
        </h2>
        <Link className="card-link" to="/evaluation">
          Open Evaluation
        </Link>
      </div>
      <div className="p-4">
        {!loaded ? (
          <p className="text-sm text-slate-500">Loading resilience evidence…</p>
        ) : experimentCount === 0 ? (
          <p className="text-sm text-slate-500">
            No completed evaluation experiments yet. Run one from Evaluation to see the Aegis
            Resilience Score and Mission Continuity Index here.
          </p>
        ) : (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <dt className="text-slate-500">Aegis Resilience Score</dt>
            <dd className="text-slate-900">
              {meanArs === null ? 'N/A' : `${meanArs.toFixed(1)} / 100`}
            </dd>
            <dt className="text-slate-500">Mission Continuity Index</dt>
            <dd className="text-slate-900">{meanMci === null ? 'N/A' : meanMci.toFixed(3)}</dd>
            <dt className="text-slate-500">Based on</dt>
            <dd className="text-slate-900">
              {experimentCount} completed experiment{experimentCount === 1 ? '' : 's'}
            </dd>
          </dl>
        )}
      </div>
    </section>
  )
}
