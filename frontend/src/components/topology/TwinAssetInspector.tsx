import { Check, CircleAlert, Info, Play, TriangleAlert, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { useAutonomyWorkflow } from '../../hooks/useAutonomyWorkflow'
import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { formatClock } from '../../lib/activity'
import { humanize, orchestrationState } from '../../lib/orchestrationState'
import type { CandidatePlanAssessment } from '../../types/bluePlanning'
import type { Orchestration } from '../../types/orchestration'
import type { InfrastructureEdge, InfrastructureNode } from '../../types/topology'
import { Button } from '../ui/button'
import { KeyValue } from '../ui/panel'
import { useDecisionActions } from '../workflow/useDecisionActions'

type Tab = 'overview' | 'events' | 'recommendations' | 'history'

const SEVERITY_ICON: Record<string, ReactNode> = {
  technique: <TriangleAlert className="text-[var(--danger)]" aria-hidden="true" />,
  anomalous: <TriangleAlert className="text-[var(--warn)]" aria-hidden="true" />,
  normal: <Info className="text-[var(--accent)]" aria-hidden="true" />,
}

/** True when a candidate plan would act on this asset or one of its links. */
function touches(candidate: CandidatePlanAssessment, assetId: string) {
  return (
    candidate.target_id === assetId ||
    candidate.target_id.split('--').includes(assetId) ||
    candidate.changed_node_ids.includes(assetId) ||
    candidate.changed_edge_ids.some((id) => id.split('--').includes(assetId))
  )
}

function stateOf(
  node: InfrastructureNode,
  orchestration: Orchestration | null,
  live: ReturnType<typeof useSimulationPlayback>['liveTopology'],
  incidentAssets: string[],
): { label: string; tone: 'danger' | 'warn' | 'ok' | 'accent' | 'neutral' | 'predicted' } {
  const execution = orchestration?.executions[0]
  const executed =
    execution &&
    (execution.changed_node_ids.includes(node.asset_id) ||
      execution.changed_edge_ids.some((id) => id.split('--').includes(node.asset_id)))
  if (executed && execution.execution_state === 'rolled_back_simulated')
    return { label: 'Restored', tone: 'ok' }
  if (executed && execution.execution_state === 'completed_simulated')
    return { label: 'Mitigated (simulated)', tone: 'accent' }
  const liveNode = live.nodes[node.asset_id]
  if (liveNode?.correlated || incidentAssets.includes(node.asset_id))
    return { label: 'Incident evidence', tone: 'danger' }
  if (liveNode?.anomalous_observed) return { label: 'Anomalous', tone: 'warn' }
  if (liveNode?.predicted) return { label: 'Predicted target', tone: 'predicted' }
  if (liveNode?.observed) return { label: 'Observed', tone: 'neutral' }
  return { label: 'Nominal', tone: 'ok' }
}

/**
 * Inspector for one synthetic asset: identity and metadata, the replayed
 * events that touched it, the Blue Agent's candidate actions that would act
 * on it (with the real human gate for the selected plan), and its timeline.
 */
export function TwinAssetInspector({
  node,
  edges,
  onClose,
  icon,
}: {
  node: InfrastructureNode | null
  edges: InfrastructureEdge[]
  onClose: () => void
  icon: ReactNode
}) {
  const playback = useSimulationPlayback()
  const workflow = useAutonomyWorkflow()
  const actions = useDecisionActions()
  const [tab, setTab] = useState<Tab>('overview')

  if (!node)
    return (
      <section className="panel asset-inspector" id="twin-inspector" aria-label="Selected asset">
        <div className="empty-state h-full">
          <Info className="size-6" />
          <strong>No asset selected</strong>
          <span>
            Select an asset on the canvas, or search for one in the header, to inspect its evidence
            and the defensive actions that would affect it.
          </span>
        </div>
      </section>
    )

  const live = playback.liveTopology
  const liveNode = live.nodes[node.asset_id]
  const incidentAssets = playback.currentIncidentCandidate?.involved_asset_ids ?? []
  const state = stateOf(node, workflow.orchestration, live, incidentAssets)
  const techniquesByEvent = new Map<string, string[]>()
  for (const item of playback.techniqueTimeline)
    techniquesByEvent.set(item.event_id, [
      ...(techniquesByEvent.get(item.event_id) ?? []),
      `${item.technique_id} · ${item.technique_name}`,
    ])
  const events = playback.events
    .filter((event) => event.source_id === node.asset_id || event.destination_id === node.asset_id)
    .reverse()
  const candidates = (workflow.result?.comparison?.candidates ?? []).filter((candidate) =>
    touches(candidate, node.asset_id),
  )
  const history = live.history.filter(
    (item) => item.source_asset_id === node.asset_id || item.destination_asset_id === node.asset_id,
  )
  const incoming = edges.filter((edge) => edge.destination_asset_id === node.asset_id)
  const outgoing = edges.filter((edge) => edge.source_asset_id === node.asset_id)
  const internetFacing = incoming.some((edge) => edge.source_asset_id.startsWith('external-'))
  const metadata = Object.entries(node.metadata).filter(
    ([, value]) =>
      typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean',
  )

  const eventRow = (event: (typeof events)[number]) => {
    const techniques = techniquesByEvent.get(event.event_id) ?? []
    const assessment = playback.assessmentsByEventId[event.event_id]
    const kind = techniques.length
      ? 'technique'
      : assessment?.classification === 'anomalous'
        ? 'anomalous'
        : 'normal'
    return (
      <li key={event.event_id}>
        {SEVERITY_ICON[kind]}
        <span className="min-w-0">
          <p title={`${event.event_type} · ${event.action} · ${event.outcome}`}>
            {humanize(event.event_type)} · {humanize(event.action)} ({event.outcome})
          </p>
          <small>
            {techniques[0] ??
              (assessment
                ? `${assessment.classification} · score ${assessment.hybrid_anomaly_score.toFixed(2)}`
                : 'not assessed')}
          </small>
        </span>
        <time>{formatClock(event.timestamp).slice(0, 5)}</time>
      </li>
    )
  }

  const candidateRow = (candidate: CandidatePlanAssessment) => (
    <li key={candidate.recommendation_id}>
      <span className="min-w-0">
        <p className="rec-name" title={candidate.playbook_name}>
          {candidate.playbook_name}
        </p>
        <p className="rec-target">
          {humanize(candidate.action_type)} · utility {candidate.utility_score.total.toFixed(0)} ·{' '}
          {candidate.policy_pass ? 'policy pass' : 'policy blocked'}
        </p>
      </span>
      <span className={`sev sev-${candidate.operational_impact}`}>
        {candidate.operational_impact} impact
      </span>
      {candidate.recommended && actions.pending ? (
        <Button
          size="sm"
          variant="soft"
          disabled={!actions.canApprove || actions.busy}
          title={actions.canApprove ? undefined : 'Requires ADMIN'}
          onClick={() => {
            actions.open('approve')
          }}
        >
          <Check /> Approve
        </Button>
      ) : candidate.recommended && actions.canExecuteApproved ? (
        <Button
          size="sm"
          variant="soft"
          disabled={!actions.canOperate || actions.busy}
          onClick={actions.executeApproved}
        >
          <Play /> Execute
        </Button>
      ) : candidate.recommended ? (
        <span
          className={`state-pill tone-${workflow.orchestration ? orchestrationState(workflow.orchestration.current_state).tone : 'accent'}`}
        >
          {workflow.orchestration
            ? orchestrationState(workflow.orchestration.current_state).label
            : 'Selected'}
        </span>
      ) : (
        <span className="rec-status">Not selected</span>
      )}
    </li>
  )

  const TABS: { id: Tab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'events', label: `Events (${String(events.length)})` },
    { id: 'recommendations', label: `Actions (${String(candidates.length)})` },
    { id: 'history', label: 'History' },
  ]

  return (
    <section className="panel asset-inspector" id="twin-inspector" aria-label="Selected asset">
      <header className="asset-head">
        <span
          className={`asset-head-icon${state.tone === 'danger' ? ' tone-danger' : state.tone === 'warn' ? ' tone-warn' : ''}`}
          aria-hidden="true"
        >
          {icon}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2>{node.display_name}</h2>
            <span className={`state-pill tone-${state.tone}`}>{state.label}</span>
          </div>
          <p>
            {humanize(node.asset_type)} · <span className="mono">{node.asset_id}</span>
          </p>
        </div>
        <button type="button" className="icon-btn" onClick={onClose} aria-label="Close inspector">
          <X aria-hidden="true" />
        </button>
      </header>
      <div className="line-tabs" role="tablist" aria-label="Asset views">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className="line-tab"
            onClick={() => {
              setTab(item.id)
            }}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="panel-body is-scroll pt-1">
        {tab === 'overview' ? (
          <>
            <div className="asset-facts">
              <div>
                <span>Anomaly score</span>
                <strong
                  className={liveNode?.anomalous_observed ? 'text-[var(--danger-text)]' : undefined}
                >
                  {liveNode?.anomaly_score != null ? liveNode.anomaly_score.toFixed(2) : '—'}
                </strong>
              </div>
              <div>
                <span>Criticality</span>
                <strong>{node.criticality}</strong>
              </div>
              <div>
                <span>Exposure</span>
                <strong>{internetFacing ? 'Internet-facing' : humanize(node.zone)}</strong>
              </div>
            </div>
            <p className="asset-section-title">Metadata</p>
            <KeyValue
              left
              rows={[
                ['Zone', humanize(node.zone)],
                ['Sensitivity', humanize(node.sensitivity)],
                ['Inbound', incoming.map((edge) => edge.source_asset_id).join(', ') || 'none'],
                [
                  'Outbound',
                  outgoing.map((edge) => edge.destination_asset_id).join(', ') || 'none',
                ],
                ...metadata
                  .slice(0, 6)
                  .map(([key, value]) => [humanize(key), String(value)] as [string, string]),
              ]}
            />
            <p className="m-0 mt-2 text-[0.74rem] text-[var(--text-faint)]">{node.description}</p>
            <div className="flex items-center justify-between">
              <p className="asset-section-title">Recent events</p>
              {events.length > 3 ? (
                <button
                  type="button"
                  className="card-link"
                  onClick={() => {
                    setTab('events')
                  }}
                >
                  View all
                </button>
              ) : null}
            </div>
            {events.length ? (
              <ul className="event-list">{events.slice(0, 3).map(eventRow)}</ul>
            ) : (
              <p className="m-0 text-[0.76rem] text-[var(--text-faint)]">
                No replayed telemetry touches this asset.
              </p>
            )}
            <div className="flex items-center justify-between">
              <p className="asset-section-title">Recommended actions ({candidates.length})</p>
              {candidates.length > 2 ? (
                <button
                  type="button"
                  className="card-link"
                  onClick={() => {
                    setTab('recommendations')
                  }}
                >
                  View all
                </button>
              ) : null}
            </div>
            {candidates.length ? (
              <ul className="rec-list">{candidates.slice(0, 2).map(candidateRow)}</ul>
            ) : (
              <p className="m-0 text-[0.76rem] text-[var(--text-faint)]">
                {workflow.result?.comparison
                  ? 'No candidate plan acts on this asset.'
                  : 'Candidate plans appear once the Blue workflow ranks responses.'}
              </p>
            )}
          </>
        ) : null}
        {tab === 'events' ? (
          events.length ? (
            <ul className="event-list">{events.map(eventRow)}</ul>
          ) : (
            <p className="empty-state">No replayed telemetry touches this asset.</p>
          )
        ) : null}
        {tab === 'recommendations' ? (
          candidates.length ? (
            <ul className="rec-list">{candidates.map(candidateRow)}</ul>
          ) : (
            <p className="empty-state">
              {workflow.result?.comparison
                ? 'No candidate plan acts on this asset.'
                : 'Candidate plans appear once the Blue workflow ranks responses.'}
            </p>
          )
        ) : null}
        {tab === 'history' ? (
          history.length ? (
            <ul className="event-list">
              {[...history].reverse().map((item) => (
                <li key={item.event_id}>
                  {item.technique_ids.length ? (
                    <TriangleAlert className="text-[var(--danger)]" aria-hidden="true" />
                  ) : item.anomaly_classification === 'anomalous' ? (
                    <CircleAlert className="text-[var(--warn)]" aria-hidden="true" />
                  ) : (
                    <Info className="text-[var(--accent)]" aria-hidden="true" />
                  )}
                  <span className="min-w-0">
                    <p>
                      #{item.sequence_number} {item.source_asset_id ?? 'outside the twin'} →{' '}
                      {item.destination_asset_id ?? 'outside the twin'}
                    </p>
                    <small>
                      {humanize(item.action)} · {item.anomaly_classification ?? 'pending'}
                      {item.technique_ids.length ? ` · ${item.technique_ids.join(', ')}` : ''}
                    </small>
                  </span>
                  <time>{formatClock(item.timestamp).slice(0, 5)}</time>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty-state">History appears as the replay touches this asset.</p>
          )
        ) : null}
      </div>
      {actions.element}
    </section>
  )
}
