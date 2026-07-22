import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { useSystemData } from '../../hooks/useSystemData'
import { DEMO_MODE } from '../../lib/constants'
import { Card, CardContent, CardHeader } from '../ui/card'

type StageState = 'waiting' | 'ready' | 'completed' | 'attention required' | 'failed'

export function JudgeDemoGuide() {
  const { health } = useSystemData()
  const playback = useSimulationPlayback()
  const [cuesVisible, setCuesVisible] = useState(DEMO_MODE)
  if (!DEMO_MODE) return null

  const anomalySeen = playback.assessmentTimeline.length > 0
  const techniqueSeen = playback.techniqueTimeline.length > 0
  const correlated = playback.currentIncidentCandidate !== null
  const predicted = playback.predictionTimeline.length > 0
  const stages: Array<{ label: string; state: StageState; href?: string }> = [
    {
      label: 'Environment Ready',
      state: health?.status === 'healthy' ? 'completed' : health ? 'failed' : 'waiting',
    },
    {
      label: 'Model Ready',
      state: playback.models.length
        ? 'completed'
        : playback.modelsLoading
          ? 'waiting'
          : 'attention required',
      href: '/model-analytics',
    },
    { label: 'Scenario Selected', state: playback.activeRun ? 'completed' : 'ready' },
    { label: 'Playback Started', state: playback.activeRun ? 'completed' : 'waiting' },
    {
      label: 'First Anomaly Observed',
      state: anomalySeen ? 'completed' : playback.detectionError ? 'failed' : 'waiting',
    },
    {
      label: 'MITRE Technique Observed',
      state: techniqueSeen ? 'completed' : playback.correlationError ? 'failed' : 'waiting',
      href: '/mitre',
    },
    {
      label: 'Incident Candidate Correlated',
      state: correlated ? 'completed' : 'waiting',
      href: '/incidents',
    },
    {
      label: 'Next Stage Predicted',
      state: predicted ? 'completed' : playback.predictionError ? 'failed' : 'waiting',
      href: '/predictive-analytics',
    },
    { label: 'Response Recommendations Generated', state: 'ready', href: '/response-centre' },
    { label: 'Agentic Orchestration Created', state: 'waiting', href: '/response-operations' },
    { label: 'Human Approval Recorded', state: 'waiting', href: '/response-operations' },
    { label: 'Executed in Synthetic Twin', state: 'waiting', href: '/response-operations' },
    { label: 'Simulated Outcome Verified', state: 'waiting', href: '/response-operations' },
    { label: 'Synthetic State Rolled Back', state: 'waiting', href: '/response-operations' },
    { label: 'Audit Chain Verified', state: 'waiting', href: '/audit-trail' },
  ]
  const cue = !playback.activeRun
    ? 'Select Start Synthetic Simulation when you are ready; nothing starts automatically.'
    : !anomalySeen
      ? 'Normal synthetic activity is currently being replayed.'
      : !techniqueSeen
        ? 'Repeated failures now deviate from the learned synthetic baseline.'
        : !predicted
          ? 'Observed evidence is correlated before any next-stage hypothesis is shown.'
          : 'Dashed routes are hypotheses, not observed activity. No real infrastructure action is executed.'

  return (
    <Card className="xl:col-span-2" aria-label="Judge Demo Guide">
      <CardHeader>
        <div>
          <p className="eyebrow">Judge Demo Mode</p>
          <h2 className="panel-title">Live synthetic demonstration guide</h2>
        </div>
        <button
          className="text-sm text-cyan-200 underline"
          onClick={() => {
            setCuesVisible((value) => !value)
          }}
        >
          {cuesVisible ? 'Hide presenter cues' : 'Show presenter cues'}
        </button>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-sm text-cyan-100">
          Judge Demo Mode prepares deterministic synthetic configuration. All analytics and response
          outputs are still computed by AegisTwin.
        </p>
        {cuesVisible ? (
          <p className="mb-4 rounded border border-cyan-900 p-3 text-sm">{cue}</p>
        ) : null}
        <ol className="grid gap-2 md:grid-cols-2">
          {stages.map((stage, index) => (
            <li
              key={stage.label}
              className="flex items-center justify-between rounded border border-slate-800 p-2 text-sm"
            >
              <span>
                {index + 1}.{' '}
                {stage.href ? (
                  <Link className="text-cyan-200 hover:underline" to={stage.href}>
                    {stage.label}
                  </Link>
                ) : (
                  stage.label
                )}
              </span>
              <span className="status-chip">{stage.state}</span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}
