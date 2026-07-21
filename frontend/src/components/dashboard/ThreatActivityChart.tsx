import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { sampleThreatActivity } from '../../mocks/threatActivity'
import { Card, CardContent, CardHeader } from '../ui/card'

export function ThreatActivityChart() {
  return (
    <Card>
      <CardHeader>
        <div>
          <p className="eyebrow">Sample synthetic activity</p>
          <h2 className="panel-title">Threat Activity</h2>
        </div>
        <span className="phase-label">Illustrative</span>
      </CardHeader>
      <CardContent>
        <div className="h-56" aria-label="Sample synthetic threat activity chart">
          <ResponsiveContainer width="100%" height="100%" minWidth={320} minHeight={224}>
            <AreaChart
              data={sampleThreatActivity}
              margin={{ top: 8, right: 4, left: -28, bottom: 0 }}
            >
              <defs>
                <linearGradient id="activityFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--color-cyan-400)" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="var(--color-cyan-400)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--color-slate-800)" vertical={false} />
              <XAxis
                dataKey="time"
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
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{
                  background: '#0b1728',
                  border: '1px solid #253247',
                  borderRadius: 8,
                }}
              />
              <Area
                type="monotone"
                dataKey="activity"
                stroke="var(--color-cyan-400)"
                fill="url(#activityFill)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
