import {
  ArrowRight,
  Boxes,
  Play,
  RotateCcw,
  Search,
  ShieldCheck,
  Swords,
  TriangleAlert,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { KpiCard, MiniColumns, Spark } from '../components/command/KpiCard'
import { RecentIncidents } from '../components/command/RecentIncidents'
import { RedAgentActivity } from '../components/command/RedAgentActivity'
import { ResponseStatus } from '../components/command/ResponseStatus'
import { CyberDigitalTwin } from '../components/topology/CyberDigitalTwin'
import { LayersMenu } from '../components/topology/LayersMenu'
import { DEFAULT_VIEW_OPTIONS } from '../components/topology/twinView'
import { TwinStateBanner } from '../components/topology/TwinLegend'
import { Button } from '../components/ui/button'
import { useAutonomyWorkflow } from '../hooks/useAutonomyWorkflow'
import { useRangeActivity } from '../hooks/useRangeActivity'
import { useSimulationPlayback } from '../hooks/useSimulationPlayback'
import { useTopology } from '../hooks/useTopology'
import { bucketActivity } from '../lib/activity'
import { derivePosture } from '../lib/posture'
import type { InfrastructureNode } from '../types/topology'

const SINK_TYPE = 'synthetic_external_sink'

const CRITICALITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f59e0b',
  medium: '#3b82f6',
  low: '#94a3b8',
}

const PREVIEW_LEGEND = [
  { label: 'Nominal', color: '#22c55e' },
  { label: 'Anomalous', color: '#f59e0b' },
  { label: 'Incident evidence', color: '#ef4444' },
  { label: 'Mitigated', color: '#2563eb' },
  { label: 'Proposed', color: '#7c3aed' },
]

/**
 * Command Centre: the at-a-glance overview. Four indicators, the live twin as
 * the dominant view, what the agents are doing now, and recent activity.
 * Analytics, evidence and detailed controls live on their own pages. Every
 * value is derived from persisted records; absent data is shown as "—".
 */
export function OverviewPage() {
  const playback = useSimulationPlayback()
  const workflow = useAutonomyWorkflow()
  const { topology } = useTopology(playback.activeRun?.scenario_id === 'staged-compromise-demo')
  const { orchestration, result } = workflow
  const [view, setView] = useState(DEFAULT_VIEW_OPTIONS)
  const activity = useRangeActivity(
    playback.runs,
    `${orchestration?.orchestration_id ?? ''}:${orchestration?.updated_at ?? ''}:${playback.currentIncidentCandidate?.incident_candidate_id ?? ''}`,
  )

  const posture = derivePosture({
    run: playback.activeRun,
    playbackState: playback.playbackState,
    assessments: playback.assessmentTimeline,
    incident: playback.currentIncidentCandidate,
    orchestration,
    result,
  })
  const selected = result?.comparison?.candidates.find((item) => item.recommended) ?? null
  const execution = orchestration?.executions[0] ?? null
  const proposal = useMemo(
    () =>
      view.showProposed && selected && !execution
        ? {
            changed_node_ids: selected.changed_node_ids,
            changed_edge_ids: selected.changed_edge_ids,
          }
        : null,
    [execution, selected, view.showProposed],
  )
  const assets: InfrastructureNode[] = useMemo(
    () => topology?.nodes.filter((node) => node.asset_type !== SINK_TYPE) ?? [],
    [topology],
  )
  const relationships =
    topology?.edges.filter(
      (edge) =>
        assets.some((node) => node.asset_id === edge.source_asset_id) &&
        assets.some((node) => node.asset_id === edge.destination_asset_id),
    ).length ?? 0
  const anomalies = playback.assessmentTimeline.filter(
    (item) => item.classification === 'anomalous',
  ).length
  const buckets = useMemo(
    () => bucketActivity(playback.events, playback.assessmentsByEventId, 8),
    [playback.assessmentsByEventId, playback.events],
  )

  // Incidents still open: correlated, not closed, and not yet contained or restored.
  const open = activity.incidents.filter(
    (item) =>
      item.incident.correlation_state !== 'closed' &&
      !['verified', 'synthetic_rollback_completed'].includes(
        item.orchestration?.current_state ?? '',
      ),
  )
  const priorityCount = (priority: string) =>
    open.filter((item) => item.incident.priority === priority).length
  const executions = activity.orchestrations.flatMap((item) => item.executions)
  const verified = activity.orchestrations.filter((item) =>
    item.verifications.some((check) => check.verification_status === 'successful_simulation'),
  ).length
  const rolledBack = activity.orchestrations.filter((item) => item.rollback !== null).length
  const failed = executions.filter((item) => item.execution_state === 'failed_simulated').length

  // One primary action, chosen by what the range needs next.
  const primary = !playback.activeRun ? (
    <Button asChild variant="brand">
      <Link to="/red-agent">
        <Swords /> Launch simulation
      </Link>
    </Button>
  ) : workflow.canRun && !result && workflow.status !== 'running' && !orchestration ? (
    <Button
      variant="brand"
      onClick={() => void workflow.runWorkflow()}
      disabled={!(workflow.session?.can_operate ?? false)}
    >
      <Play /> Run Blue workflow
    </Button>
  ) : null

  return (
    <div className="page-stack cc-page">
      <div className="cc-head">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1>Command Centre</h1>
            <span className={`posture-hero posture-chip tone-${posture.tone}`}>
              <span className={`posture-orb${posture.live ? ' is-live' : ''}`} aria-hidden="true" />
              {posture.label}
            </span>
          </div>
          <p>{posture.summary}</p>
        </div>
        <div className="btn-row">
          {!playback.activeRun && playback.lastRun ? (
            <Button
              variant="outline"
              onClick={playback.resumeLastRun}
              title="Re-stream the persisted evidence of the last run in this browser session"
            >
              <RotateCcw /> Resume last run
            </Button>
          ) : null}
          {primary}
        </div>
      </div>

      <div className="kpi-row" role="group" aria-label="Key indicators">
        <KpiCard
          icon={<Boxes />}
          tone="lavender"
          label="Digital Twin Assets"
          value={assets.length || '—'}
          sub={
            assets.length
              ? `${String(relationships)} relationships · ${String(new Set(assets.map((node) => node.zone)).size)} zones`
              : 'topology unavailable'
          }
          visual={
            <MiniColumns
              label="Assets by criticality"
              parts={['critical', 'high', 'medium', 'low'].map((level) => ({
                key: level.charAt(0).toUpperCase(),
                label: `${level} criticality`,
                value: assets.filter((node) => node.criticality === level).length,
                color: CRITICALITY_COLORS[level] ?? '#94a3b8',
              }))}
            />
          }
        />
        <KpiCard
          icon={<TriangleAlert />}
          tone="red"
          label="Active Incidents"
          value={activity.loading && open.length === 0 ? '—' : open.length}
          title="Correlated incidents in the 6 most recent runs that are not yet contained"
          sub={
            open.length
              ? `${String(priorityCount('critical'))} critical · ${String(priorityCount('high'))} high · ${String(priorityCount('medium'))} medium`
              : 'none open in recent runs'
          }
        />
        <KpiCard
          icon={<Search />}
          tone="lavender"
          label="Anomalies Detected"
          value={playback.activeRun ? anomalies : '—'}
          sub={
            playback.activeRun
              ? `of ${String(playback.assessmentTimeline.length)} assessed · current run`
              : 'no run in progress'
          }
          visual={
            playback.activeRun ? (
              <Spark
                tone="violet"
                label="Anomalous events across the run timeline"
                values={buckets.map((bucket) => bucket.anomalous)}
              />
            ) : undefined
          }
        />
        <KpiCard
          icon={<ShieldCheck />}
          tone="green"
          label="Mitigations Executed"
          value={activity.loading && executions.length === 0 ? '—' : executions.length}
          unit="synthetic"
          title="Synthetic executions recorded across every orchestration"
          sub={
            executions.length
              ? `Verified ${String(verified)} · Rolled back ${String(rolledBack)}`
              : 'none recorded yet'
          }
          visual={
            <MiniColumns
              label="Executions by outcome"
              parts={[
                { key: 'V', label: 'verified', value: verified, color: '#22c55e' },
                { key: 'R', label: 'rolled back', value: rolledBack, color: '#3b82f6' },
                { key: 'F', label: 'failed', value: failed, color: '#ef4444' },
              ]}
            />
          }
        />
      </div>

      <div className="cc-main">
        <section className="panel cc-twin-card" aria-label="Cloud Digital Twin">
          <header className="panel-head">
            <div className="min-w-0">
              <h2 className="panel-title">Infrastructure twin</h2>
              <p className="panel-subtitle">
                {assets.length} synthetic assets
                {playback.activeRun
                  ? ` · replay ${String(playback.currentEventIndex)}/${String(playback.totalEventCount)}`
                  : ' · no replay running'}
              </p>
            </div>
            <div className="btn-row">
              <LayersMenu value={view} onChange={setView} label="View options" showMotion={false} />
              <Link className="card-link" to="/digital-twin">
                Open twin <ArrowRight className="size-3.5" />
              </Link>
            </div>
          </header>
          <div className="cc-canvas">
            {topology ? (
              <CyberDigitalTwin
                topology={topology}
                runState={null}
                liveOverlay={playback.liveTopology}
                animationPaused={playback.playbackState === 'paused'}
                responseImpact={proposal}
                syntheticExecution={execution}
                layers={view.layers}
                variant="preview"
                focusActive={
                  playback.playbackState === 'playing' || playback.playbackState === 'paused'
                }
              />
            ) : (
              <p className="empty-state h-full">Loading synthetic cloud topology…</p>
            )}
            <TwinStateBanner
              execution={execution}
              proposedCount={
                proposal ? proposal.changed_node_ids.length + proposal.changed_edge_ids.length : 0
              }
              attackActive={playback.playbackState === 'playing'}
            />
          </div>
          <footer className="legend-inline cc-legend" aria-label="Twin legend">
            {PREVIEW_LEGEND.map((item) => (
              <span key={item.label}>
                <i style={{ background: item.color }} />
                {item.label}
              </span>
            ))}
          </footer>
        </section>
        <ResponseStatus />
      </div>

      <div className="cc-lower">
        <RedAgentActivity limit={5} />
        <RecentIncidents
          items={activity.incidents}
          loading={activity.loading}
          scenarios={playback.scenarios}
          compact
        />
      </div>
    </div>
  )
}
