import { useEffect, useState } from 'react'

import { getRunIncidents } from '../services/correlationApi'
import { listOrchestrations } from '../services/orchestrationApi'
import type { IncidentCandidate } from '../types/correlation'
import type { Orchestration } from '../types/orchestration'
import type { SimulationRun } from '../types/simulation'

export interface RecentIncident {
  incident: IncidentCandidate
  run: SimulationRun
  orchestration: Orchestration | null
}

export interface RangeActivity {
  orchestrations: Orchestration[]
  incidents: RecentIncident[]
  loading: boolean
  error: string | null
}

const RECENT_RUNS = 6

/** Backend timestamps are UTC; some are serialised without an offset. */
export function parseUtc(value: string): Date {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`)
}

/**
 * Cross-run activity for dashboards: every persisted orchestration and the
 * incident candidates of the most recent runs, joined to the orchestration
 * that responded to them. Re-fetched whenever `refreshKey` changes.
 */
export function useRangeActivity(runs: SimulationRun[], refreshKey: string): RangeActivity {
  const [state, setState] = useState<RangeActivity>({
    orchestrations: [],
    incidents: [],
    loading: true,
    error: null,
  })
  const recent = [...runs]
    .sort((left, right) => right.created_at.localeCompare(left.created_at))
    .slice(0, RECENT_RUNS)
  const runKey = recent.map((run) => run.simulation_run_id).join(',')

  useEffect(() => {
    let cancelled = false
    void Promise.allSettled([
      listOrchestrations(),
      ...recent.map((run) => getRunIncidents(run.simulation_run_id)),
    ]).then(([orchestrationResult, ...incidentResults]) => {
      if (cancelled) return
      const orchestrations =
        orchestrationResult.status === 'fulfilled' ? orchestrationResult.value : []
      const byIncident = new Map<string, Orchestration>()
      for (const item of [...orchestrations].sort((left, right) =>
        left.updated_at.localeCompare(right.updated_at),
      ))
        byIncident.set(item.incident_candidate_id, item)
      const incidents: RecentIncident[] = []
      incidentResults.forEach((result, index) => {
        const run = recent[index]
        if (result.status !== 'fulfilled' || !run) return
        for (const incident of result.value.items)
          incidents.push({
            incident,
            run,
            orchestration: byIncident.get(incident.incident_candidate_id) ?? null,
          })
      })
      incidents.sort((left, right) => right.run.created_at.localeCompare(left.run.created_at))
      setState({
        orchestrations,
        incidents,
        loading: false,
        error:
          orchestrationResult.status === 'rejected'
            ? 'Orchestration history is unavailable.'
            : null,
      })
    })
    return () => {
      cancelled = true
    }
    // `recent` is fully described by runKey.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runKey, refreshKey])

  return state
}
