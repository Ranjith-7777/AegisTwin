import type { AnomalyAssessment } from '../types/detection'
import type { TelemetryEvent } from '../types/simulation'

/** HH:MM:SS of a synthetic (UTC) timestamp - the range's logical clock. */
export function formatClock(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toISOString().slice(11, 19)
}

/** "2026-10-07 15:36" in UTC. */
export function formatStamp(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
  if (Number.isNaN(date.getTime())) return '—'
  return `${date.toISOString().slice(0, 10)} ${date.toISOString().slice(11, 16)}`
}

export const SEVERITY_SERIES = ['critical', 'high', 'medium', 'low'] as const
export type SeveritySeries = (typeof SEVERITY_SERIES)[number]

export interface ActivityBucket {
  label: string
  critical: number
  high: number
  medium: number
  low: number
  anomalous: number
  total: number
}

/**
 * Groups replayed telemetry into equal slices of the run's synthetic
 * timeline, counting events by severity and anomalous assessments. Empty
 * input yields no buckets - callers render an empty state, never zeros.
 */
export function bucketActivity(
  events: TelemetryEvent[],
  assessments: Record<string, AnomalyAssessment>,
  maxBuckets = 24,
): ActivityBucket[] {
  if (events.length === 0) return []
  const times = events.map((event) => new Date(event.timestamp).getTime())
  const first = Math.min(...times)
  const last = Math.max(...times)
  const count = Math.max(1, Math.min(maxBuckets, events.length))
  const span = Math.max(1, last - first)
  const buckets: ActivityBucket[] = Array.from({ length: count }, (_, index) => ({
    label: formatClock(new Date(first + (span * index) / count).toISOString()).slice(0, 5),
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    anomalous: 0,
    total: 0,
  }))
  events.forEach((event, index) => {
    const position = Math.min(
      count - 1,
      Math.floor((((times[index] ?? first) - first) / span) * count),
    )
    const bucket = buckets[position]
    if (!bucket) return
    const severity: SeveritySeries =
      event.severity === 'critical' || event.severity === 'high' || event.severity === 'medium'
        ? event.severity
        : 'low'
    bucket[severity] += 1
    bucket.total += 1
    if (assessments[event.event_id]?.classification === 'anomalous') bucket.anomalous += 1
  })
  return buckets
}
