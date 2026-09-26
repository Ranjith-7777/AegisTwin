import { Boxes, FileBarChart, ShieldAlert, Swords } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { CommandKpiRow } from '../components/dashboard/CommandKpiRow'
import { SecurityPostureWidget } from '../components/dashboard/SecurityPostureWidget'
import type { ActivityItem } from '../components/dashboard/RecentActivity'
import { Button } from '../components/ui/button'
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

  const incident = playback.currentIncidentCandidate
  const components = recommendation?.defense_components
  const slaImpact = components ? components.sla_penalty + components.service_disruption : 0

  return (
    <div className="viewport-page">
      <div className="command-header">
        <div>
          <h1>Command Centre</h1>
          <p>Autonomous cloud security overview</p>
        </div>
        <span className="command-header-status">
          <span className="chip-dot" aria-hidden="true" />
          Demo · Operational
        </span>
      </div>

      <CommandKpiRow state={state} />

      <div className="command-main">
        <div className="command-left">
          <section className="command-twin" aria-label="Cloud Digital Twin">
            <div className="command-twin-head">
              <h2 className="panel-title">Digital Twin</h2>
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
            {topology ? (
              <p className="command-twin-foot">
                {topology.nodes.length} synthetic assets · {topology.edges.length} relationships
              </p>
            ) : null}
          </section>

          <section className="command-activity" aria-label="Recent activity">
            <div className="command-activity-head">
              <h2>Recent Activity</h2>
            </div>
            <div className="activity-table-scroll">
              <table className="activity-table">
                <thead>
                  <tr>
                    <th>Stage</th>
                    <th>Detail</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {activityItems.map((item) => (
                    <tr key={item.label}>
                      <td className="is-primary">{item.label}</td>
                      <td>{item.detail}</td>
                      <td>
                        <span
                          className={
                            item.done ? 'activity-status is-done' : 'activity-status is-pending'
                          }
                        >
                          <span className="chip-dot" aria-hidden="true" />
                          {item.done ? 'Done' : 'Pending'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <div className="command-right">
          <SecurityPostureWidget state={state} totalAssets={topology?.nodes.length ?? 0} />

          <aside className="command-panel" aria-label="Active incident">
            <div className="command-panel-section">
              <p className="command-panel-label">
                <ShieldAlert className="size-3.5" aria-hidden="true" />
                Active Incident
              </p>
              {incident ? (
                <>
                  <p className="text-sm font-semibold capitalize text-slate-900">
                    {incident.priority} priority
                  </p>
                  <p className="text-xs text-slate-500">
                    {incident.evidence_count} evidence items ·{' '}
                    {incident.observed_technique_ids.length} MITRE techniques
                  </p>
                  <Link className="card-link text-xs" to="/incidents">
                    View incident →
                  </Link>
                </>
              ) : (
                <p className="text-sm text-slate-500">
                  No active incidents. Correlated evidence will appear here once detected.
                </p>
              )}
            </div>
            <div className="command-panel-section">
              <p className="command-panel-label">Blue Agent Response</p>
              {recommendation && components ? (
                <>
                  <p className="text-sm font-semibold text-slate-900">
                    {recommendation.playbook_name}
                  </p>
                  <p className="text-xs text-slate-500">
                    Defense score {recommendation.defense_score.toFixed(2)} · +
                    {components.security_improvement.toFixed(2)} security · −
                    {slaImpact.toFixed(2)} SLA impact
                  </p>
                  <Button size="sm" disabled={busy} onClick={approve}>
                    Approve
                  </Button>
                </>
              ) : (
                <>
                  <p className="text-sm text-slate-500">
                    {error ??
                      (ready
                        ? 'No mitigation has been ranked for the current sequence.'
                        : 'Start a scenario with a detection model to rank mitigations.')}
                  </p>
                  <Button size="sm" variant="outline" disabled={!ready || busy} onClick={analyze}>
                    {busy ? 'Ranking…' : 'Rank mitigations'}
                  </Button>
                </>
              )}
            </div>
          </aside>

          <div className="quick-actions-row" aria-label="Quick actions">
            <Button
              variant="outline"
              size="sm"
              className="quick-action-btn"
              onClick={() => {
                void navigate('/red-agent')
              }}
            >
              <Swords className="size-3.5" />
              Run Scenario
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="quick-action-btn"
              onClick={() => {
                void navigate('/digital-twin')
              }}
            >
              <Boxes className="size-3.5" />
              Open Twin
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="quick-action-btn"
              onClick={() => {
                void navigate('/evaluation')
              }}
            >
              <FileBarChart className="size-3.5" />
              Report
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
