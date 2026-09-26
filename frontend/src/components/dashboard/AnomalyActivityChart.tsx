import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { Card, CardContent, CardHeader } from '../ui/card'

export function AnomalyActivityChart() {
  const { assessmentTimeline, selectedModel } = useSimulationPlayback()
  const data = assessmentTimeline.map((item) => ({
    sequence: item.sequence_number,
    score: Number(item.hybrid_anomaly_score.toFixed(4)),
  }))
  const threshold = selectedModel?.calibrated_threshold ?? null
  return (
    <Card aria-label="Anomaly activity">
      <CardHeader>
        <div>
          <p className="eyebrow">Live detection scores</p>
          <h2 className="panel-title">Anomaly Activity</h2>
        </div>
        <span className="phase-label">{data.length} assessed</span>
      </CardHeader>
      <CardContent>
        {data.length ? (
          <div className="h-56" aria-label="Hybrid anomaly score by replay sequence">
            <ResponsiveContainer width="100%" height="100%" minWidth={280} minHeight={224}>
              <AreaChart data={data} margin={{ top: 8, right: 4, left: -28, bottom: 0 }}>
                <defs>
                  <linearGradient id="anomalyFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-cyan-400)" stopOpacity={0.38} />
                    <stop offset="95%" stopColor="var(--color-cyan-400)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--color-slate-800)" vertical={false} />
                <XAxis
                  dataKey="sequence"
                  stroke="var(--color-slate-600)"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  stroke="var(--color-slate-600)"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  domain={[0, 1]}
                />
                <Tooltip
                  contentStyle={{
                    background: '#0b1728',
                    border: '1px solid #253247',
                    borderRadius: 8,
                  }}
                />
                {threshold === null ? null : (
                  <ReferenceLine y={threshold} stroke="#f59e0b" strokeDasharray="5 4" />
                )}
                <Area
                  type="monotone"
                  dataKey="score"
                  stroke="var(--color-cyan-400)"
                  fill="url(#anomalyFill)"
                  strokeWidth={2}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="text-sm text-slate-500">
            No assessments yet. Start a scenario with detection enabled to plot hybrid anomaly
            scores against the calibrated threshold.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
