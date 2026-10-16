import { ChartColumnBig } from 'lucide-react'
import { useMemo } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { bucketActivity } from '../../lib/activity'

const SERIES = [
  { key: 'critical', label: 'Critical', color: '#ef4444' },
  { key: 'high', label: 'High', color: '#f59e0b' },
  { key: 'medium', label: 'Medium', color: '#3b82f6' },
  { key: 'low', label: 'Low / info', color: '#bfdbfe' },
] as const

/**
 * Replayed synthetic telemetry of the current run, bucketed on the run's own
 * (simulated) timeline and stacked by event severity.
 */
export function ThreatActivity({ className }: { className?: string }) {
  const playback = useSimulationPlayback()
  const buckets = useMemo(
    () => bucketActivity(playback.events, playback.assessmentsByEventId),
    [playback.assessmentsByEventId, playback.events],
  )
  const anomalies = buckets.reduce((sum, bucket) => sum + bucket.anomalous, 0)
  return (
    <section className={`panel ${className ?? ''}`} aria-label="Threat activity">
      <header className="panel-head">
        <div>
          <h2 className="panel-title">Threat Activity</h2>
          <p className="panel-subtitle">
            Synthetic telemetry by severity · current run, simulated time (UTC)
          </p>
        </div>
        <div className="legend-inline">
          {SERIES.map((series) => (
            <span key={series.key}>
              <i style={{ background: series.color }} />
              {series.label}
            </span>
          ))}
        </div>
      </header>
      <div className="panel-body pt-0">
        {buckets.length > 0 ? (
          <div
            className="threat-chart"
            role="img"
            aria-label={`${String(playback.events.length)} replayed events, ${String(anomalies)} assessed anomalous`}
          >
            <ResponsiveContainer width="100%" height="100%" minWidth={240} minHeight={70}>
              <BarChart data={buckets} margin={{ top: 6, right: 4, left: -14, bottom: 0 }}>
                <CartesianGrid stroke="#eef1f6" vertical={false} />
                <XAxis
                  dataKey="label"
                  stroke="#94a3b8"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  interval="preserveStartEnd"
                  minTickGap={28}
                />
                <YAxis
                  stroke="#94a3b8"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  allowDecimals={false}
                  width={30}
                  tickCount={3}
                />
                <Tooltip
                  cursor={{ fill: 'rgba(37,99,235,0.06)' }}
                  contentStyle={{
                    border: '1px solid #e4e8ef',
                    borderRadius: 8,
                    boxShadow: '0 8px 24px -12px rgba(15,27,45,0.25)',
                    fontSize: 12,
                  }}
                />
                {SERIES.map((series, index) => (
                  <Bar
                    key={series.key}
                    dataKey={series.key}
                    name={series.label}
                    stackId="severity"
                    fill={series.color}
                    maxBarSize={14}
                    radius={index === SERIES.length - 1 ? [3, 3, 0, 0] : 0}
                    isAnimationActive={false}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="empty-state threat-chart">
            <ChartColumnBig className="size-6" />
            <span>Threat activity appears as the Red Agent replay streams telemetry.</span>
          </div>
        )}
      </div>
    </section>
  )
}
