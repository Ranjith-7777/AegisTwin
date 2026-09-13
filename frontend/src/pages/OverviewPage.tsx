import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ActiveIncidentCard } from '../components/dashboard/ActiveIncidentCard'
import { BlueAgentCard } from '../components/dashboard/BlueAgentCard'
import { DetectionSummaryCard } from '../components/dashboard/DetectionSummaryCard'
import { KpiCards } from '../components/dashboard/KpiCards'
import { MissionProgress, type StageKey } from '../components/dashboard/MissionProgress'
import { RecentActivity, type ActivityItem } from '../components/dashboard/RecentActivity'
import { RiskGauge } from '../components/dashboard/RiskGauge'
import { PageHeader } from '../components/layout/PageHeader'
import { RedAgentPanel } from '../components/simulation/RedAgentPanel'
import { CyberDigitalTwin } from '../components/topology/CyberDigitalTwin'
import { useSimulationPlayback } from '../hooks/useSimulationPlayback'
import { useTopology } from '../hooks/useTopology'
import { deriveCommandCentreState } from '../lib/commandCentre'
import { createOrchestration, listOrchestrations } from '../services/orchestrationApi'
import { analyzeResponses, getResponseSummary } from '../services/responseApi'
import type { ResponseRecommendation } from '../types/response'

export function OverviewPage() {
  const playback = useSimulationPlayback()
  const navigate = useNavigate()
  const stagedScenario = playback.activeRun?.scenario_id === 'staged-compromise-demo'
  const { topology } = useTopology(stagedScenario)
  // Held with the run/model key it belongs to so a stale result is never shown.
  const [analysed, setAnalysed] = useState<{ key: string; item: ResponseRecommendation | null }>({
    key: '',
    item: null,
  })
  const [recovered, setRecovered] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runId = playback.activeRun?.simulation_run_id ?? ''
  const modelId = playback.selectedModel?.model_id ?? ''
  const sequence = playback.currentEventIndex
  const ready = Boolean(runId && modelId && sequence > 0)
  const analysisKey = `${runId}:${modelId}`
  const recommendation = analysed.key === analysisKey && runId ? analysed.item : null

  useEffect(() => {
    if (!runId || !modelId) return
    let cancelled = false
    void getResponseSummary(runId, modelId)
      .then((summary) => {
        if (!cancelled)
          setAnalysed({ key: `${runId}:${modelId}`, item: summary.top_recommendation })
      })
      .catch(() => {
        if (!cancelled) setAnalysed({ key: `${runId}:${modelId}`, item: null })
      })
    return () => {
      cancelled = true
    }
  }, [runId, modelId, playback.playbackState])

  // "Recover" completes once a synthetic execution for this run has been rolled back.
  useEffect(() => {
    if (!runId) return
    let cancelled = false
    void listOrchestrations()
      .then((items) => {
        if (cancelled) return
        setRecovered(
          items.some(
            (item) =>
              item.simulation_run_id === runId &&
              (item.rollback !== null ||
                item.executions.some(
                  (execution) => execution.execution_state === 'rolled_back_simulated',
                )),
          ),
        )
      })
      .catch(() => {
        if (!cancelled) setRecovered(false)
      })
    return () => {
      cancelled = true
    }
  }, [runId, recommendation])

  const analyze = useCallback(() => {
    if (!ready) return
    setBusy(true)
    setError(null)
    void analyzeResponses({ runId, modelId, throughSequence: sequence, predictionEnabled: true })
      .then((result) => {
        setAnalysed({ key: `${runId}:${modelId}`, item: result.recommendations[0] ?? null })
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : 'Blue Agent ranking is unavailable.')
      })
      .finally(() => {
        setBusy(false)
      })
  }, [modelId, ready, runId, sequence])

  const approve = useCallback(() => {
    if (!recommendation) return
    setBusy(true)
    setError(null)
    void createOrchestration(recommendation.run_id, {
      model_id: recommendation.model_id,
      incident_candidate_id: recommendation.incident_candidate_id,
      selected_recommendation_id: recommendation.recommendation_id,
      through_sequence_number: recommendation.through_sequence_number,
    })
      .then(() => navigate('/blue-agent/verification'))
      .catch(() => {
        setError('Synthetic orchestration creation failed.')
      })
      .finally(() => {
        setBusy(false)
      })
  }, [navigate, recommendation])

  const state = useMemo(
    () =>
      deriveCommandCentreState({
        topology,
        live: playback.liveTopology,
        playbackState: playback.playbackState,
        hasActiveRun: playback.activeRun !== null,
        incident: playback.currentIncidentCandidate,
        prediction: playback.currentPrediction,
        mitigatedNodeIds: recommendation?.simulation?.changed_node_ids ?? [],
        hasRecommendation: recommendation !== null,
      }),
    [
      playback.activeRun,
      playback.currentIncidentCandidate,
      playback.currentPrediction,
      playback.liveTopology,
      playback.playbackState,
      recommendation,
      topology,
    ],
  )

  const completed: Record<StageKey, boolean> = {
    simulate: playback.activeRun !== null,
    detect: playback.assessmentTimeline.length > 0,
    predict: playback.predictionTimeline.length > 0,
    defend: recommendation !== null,
    recover: recovered,
  }

  const activityItems: ActivityItem[] = [
    {
      label: 'Scenario started',
      detail: playback.activeRun
        ? `${playback.activeRun.scenario_id} · seed ${String(playback.activeRun.seed)}`
        : 'No scenario has been started in this session.',
      done: playback.activeRun !== null,
    },
    {
      label: 'Anomaly detected',
      detail:
        playback.assessmentTimeline.length > 0
          ? `${String(playback.assessmentTimeline.length)} events assessed`
          : 'Awaiting scored telemetry.',
      done: playback.assessmentTimeline.some((item) => item.classification === 'anomalous'),
    },
    {
      label: 'Incident created',
      detail: playback.currentIncidentCandidate
        ? `${playback.currentIncidentCandidate.priority} priority · ${String(playback.currentIncidentCandidate.evidence_count)} evidence items`
        : 'No incident has been correlated yet.',
      done: playback.currentIncidentCandidate !== null,
    },
    {
      label: 'Response proposed',
      detail: recommendation
        ? `${recommendation.playbook_name} · defense score ${recommendation.defense_score.toFixed(2)}`
        : 'No mitigation has been ranked yet.',
      done: recommendation !== null,
    },
    {
      label: 'Verification completed',
      detail: recovered
        ? 'Synthetic execution verified and rolled back.'
        : 'Awaiting synthetic execution and verification.',
      done: recovered,
    },
  ]

  return (
    <div className="overview">
      <PageHeader
        title="Command Centre"
        subtitle="Autonomous cloud cyber-resilience overview — simulation environment"
      />
      <MissionProgress completed={completed} />
      <div className="overview-risk-row">
        <RiskGauge state={state} hasEvidence={playback.activeRun !== null} />
        <KpiCards state={state} />
      </div>
      <div className="overview-row">
        <ActiveIncidentCard incident={playback.currentIncidentCandidate} />
        <section className="card twin-panel" aria-label="Cloud Digital Twin">
          <div className="card-head">
            <h2 className="card-title">Digital Twin</h2>
            <Link className="card-link" to="/digital-twin">
              Open Digital Twin
            </Link>
          </div>
          <div className="twin-canvas-wrap">
            {topology ? (
              <CyberDigitalTwin
                topology={topology}
                runState={null}
                liveOverlay={playback.liveTopology}
                animationPaused={playback.playbackState === 'paused'}
                variant="workspace"
              />
            ) : (
              <p className="twin-loading">Loading synthetic cloud topology…</p>
            )}
          </div>
          <p className="px-4 pb-3 text-xs text-slate-500">
            {topology
              ? `${String(topology.nodes.length)} synthetic assets · ${String(topology.edges.length)} relationships`
              : null}
          </p>
        </section>
      </div>
      <div className="overview-row">
        <DetectionSummaryCard
          model={playback.selectedModel}
          assessments={playback.assessmentTimeline}
          prediction={playback.currentPrediction}
        />
        <BlueAgentCard
          recommendation={recommendation}
          busy={busy}
          ready={ready}
          error={error}
          onAnalyze={analyze}
          onApprove={approve}
        />
      </div>
      <div className="workspace">
        <RedAgentPanel state={state} />
        <RecentActivity items={activityItems} />
      </div>
    </div>
  )
}
