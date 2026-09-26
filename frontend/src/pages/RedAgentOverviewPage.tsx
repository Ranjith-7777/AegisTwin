import { useState } from 'react'

import { PageHeader } from '../components/layout/PageHeader'
import { LiveEventStream } from '../components/simulation/LiveEventStream'
import { RedAgentPanel } from '../components/simulation/RedAgentPanel'
import { RunHistory } from '../components/simulation/RunHistory'
import { useSimulationPlayback } from '../hooks/useSimulationPlayback'
import { useTopology } from '../hooks/useTopology'
import { deriveCommandCentreState } from '../lib/commandCentre'

type RedAgentTab = 'live' | 'history'

/**
 * Red Agent workspace: scenario selector and controls on the left, the
 * currently running attack (progress + recent synthetic events) on the
 * right. Deeper run history moves behind a tab instead of stacking below.
 */
export function RedAgentOverviewPage() {
  const [tab, setTab] = useState<RedAgentTab>('live')
  const playback = useSimulationPlayback()
  const stagedScenario = playback.activeRun?.scenario_id === 'staged-compromise-demo'
  const { topology } = useTopology(stagedScenario)

  const state = deriveCommandCentreState({
    topology,
    live: playback.liveTopology,
    playbackState: playback.playbackState,
    hasActiveRun: playback.activeRun !== null,
    incident: playback.currentIncidentCandidate,
    prediction: playback.currentPrediction,
    mitigatedNodeIds: [],
    hasRecommendation: false,
  })

  return (
    <div className="viewport-page">
      <PageHeader
        title="Red Agent"
        subtitle="Deterministic attack simulation and scenario control"
        actions={
          <span className={`chip chip-${state.redAgentState === 'active' ? 'danger' : 'muted'}`}>
            <span className="chip-dot" aria-hidden="true" />
            {state.redAgentState}
          </span>
        }
      />
      <div className="agent-workspace">
        <div className="agent-workspace-col">
          <RedAgentPanel state={state} />
        </div>
        <div className="agent-workspace-col">
          <div className="tab-strip" role="tablist" aria-label="Red Agent views">
            <button
              role="tab"
              aria-selected={tab === 'live'}
              className={tab === 'live' ? 'section-tab is-active' : 'section-tab'}
              onClick={() => {
                setTab('live')
              }}
            >
              Live Attack
            </button>
            <button
              role="tab"
              aria-selected={tab === 'history'}
              className={tab === 'history' ? 'section-tab is-active' : 'section-tab'}
              onClick={() => {
                setTab('history')
              }}
            >
              Run History
            </button>
          </div>
          {tab === 'live' ? (
            <div className="scroll-panel">
              <LiveEventStream expanded />
            </div>
          ) : (
            <div className="scroll-panel">
              <RunHistory />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
