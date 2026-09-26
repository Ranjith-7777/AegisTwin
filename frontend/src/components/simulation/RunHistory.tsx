import { History, RotateCcw } from 'lucide-react'

import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { EmptyState } from '../common/EmptyState'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent, CardHeader } from '../ui/card'

export function RunHistory() {
  const { runs, scenarios, replayRun, playbackState } = useSimulationPlayback()
  const scenarioNames = new Map(scenarios.map((scenario) => [scenario.scenario_id, scenario.name]))
  const playbackActive = playbackState === 'playing' || playbackState === 'paused'
  return (
    <Card className="xl:col-span-2">
      <CardHeader>
        <div>
          <p className="eyebrow">Persisted synthetic runs</p>
          <h2 className="panel-title">Run History</h2>
        </div>
        <History className="size-5 text-blue-600" />
      </CardHeader>
      <CardContent>
        {runs.length === 0 ? (
          <EmptyState
            title="No simulation runs"
            detail="Created deterministic runs will appear here without deletion controls."
          />
        ) : (
          <div className="run-history-list">
            {runs.map((run) => (
              <article key={run.simulation_run_id} className="run-history-row">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium text-slate-800">
                      {scenarioNames.get(run.scenario_id) ?? run.scenario_id}
                    </p>
                    <Badge className="border-blue-200 text-blue-600">Synthetic</Badge>
                  </div>
                  <p className="technical mt-1 truncate text-xs text-slate-500">
                    {run.simulation_run_id}
                  </p>
                </div>
                <dl>
                  <div>
                    <dt>Seed</dt>
                    <dd>{run.seed}</dd>
                  </div>
                  <div>
                    <dt>Start</dt>
                    <dd>{new Date(run.start_time).toISOString()}</dd>
                  </div>
                  <div>
                    <dt>Speed</dt>
                    <dd>{run.playback_speed}×</dd>
                  </div>
                  <div>
                    <dt>Events</dt>
                    <dd>{run.event_count}</dd>
                  </div>
                  <div>
                    <dt>Created</dt>
                    <dd>{new Date(run.created_at).toISOString()}</dd>
                  </div>
                </dl>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    replayRun(run)
                  }}
                  disabled={playbackActive}
                  aria-label={`Replay ${run.simulation_run_id}`}
                >
                  <RotateCcw className="size-4" />
                  Replay
                </Button>
              </article>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
