import { Link } from 'react-router-dom'

import { CyberDigitalTwin } from './CyberDigitalTwin'
import { useTopology } from '../../hooks/useTopology'
import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { Card, CardContent, CardHeader } from '../ui/card'

export function CompactDigitalTwin() {
  const playback = useSimulationPlayback()
  const { topology, loading, error } = useTopology(
    playback.activeRun?.scenario_id === 'staged-compromise-demo',
  )
  return (
    <Card className="xl:col-span-2">
      <CardHeader>
        <div>
          <p className="eyebrow">Versioned synthetic infrastructure</p>
          <h2 className="panel-title">Cyber Digital Twin</h2>
        </div>
        <Link className="text-sm text-cyan-300" to="/digital-twin">
          Open full topology
        </Link>
      </CardHeader>
      <CardContent>
        {loading ? <p>Loading synthetic topology…</p> : null}
        {error ? <p role="alert">{error}</p> : null}
        {topology ? (
          <>
            <p className="mb-2 text-xs text-slate-400">
              {playback.playbackState} · sequence {playback.currentEventIndex} · observed{' '}
              {Object.values(playback.liveTopology.nodes).filter((item) => item.observed).length}{' '}
              assets
            </p>
            <CyberDigitalTwin
              topology={topology}
              runState={null}
              liveOverlay={playback.liveTopology}
              animationPaused={playback.playbackState === 'paused'}
              compact
            />
          </>
        ) : null}
      </CardContent>
    </Card>
  )
}
