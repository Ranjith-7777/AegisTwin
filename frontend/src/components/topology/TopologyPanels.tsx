import type {
  InfrastructureEdge,
  InfrastructureNode,
  RunTopologyState,
  TopologyPath,
} from '../../types/topology'
import type { LiveTopologyOverlay } from '../../types/liveTopology'
import { Card, CardContent, CardHeader } from '../ui/card'

export function ZoneGroup() {
  return (
    <p className="text-xs text-slate-500">
      Zones: Edge → Cluster → Workload → Data · Identity, Management and Operations adjacent ·
      Synthetic External isolated
    </p>
  )
}

export function PathLegend() {
  return (
    <div className="topology-legend" aria-label="Topology path legend">
      {[
        'expected',
        'observed',
        'correlated',
        'predicted',
        'unexpected',
        'simulation-only external',
      ].map((item) => (
        <span key={item} className={`state-${item.replaceAll(' ', '-')}`}>
          {item}
        </span>
      ))}
    </div>
  )
}

export function TopologyStatusSummary({
  nodeCount,
  edgeCount,
  version,
}: {
  nodeCount: number
  edgeCount: number
  version: string
}) {
  return (
    <div className="playback-facts">
      <div>
        <span>Topology version</span>
        <strong>{version}</strong>
      </div>
      <div>
        <span>Synthetic assets</span>
        <strong>{nodeCount}</strong>
      </div>
      <div>
        <span>Relationships</span>
        <strong>{edgeCount}</strong>
      </div>
    </div>
  )
}

export function AssetInspector({
  node,
  edges,
  state,
  live,
  bare = false,
}: {
  node: InfrastructureNode | null
  edges: InfrastructureEdge[]
  state: RunTopologyState | null
  live?: LiveTopologyOverlay | null
  bare?: boolean
}) {
  if (!node) {
    const empty = <p className="text-slate-500">Select a synthetic asset to inspect it.</p>
    if (bare) return empty
    return (
      <Card>
        <CardHeader>
          <h2 className="panel-title">Asset Inspector</h2>
        </CardHeader>
        <CardContent>{empty}</CardContent>
      </Card>
    )
  }
  const incoming = edges.filter((edge) => edge.destination_asset_id === node.asset_id)
  const outgoing = edges.filter((edge) => edge.source_asset_id === node.asset_id)
  const liveNode = live?.nodes[node.asset_id]
  const body = (
    <div className="space-y-2 text-sm">
      <p className="technical">{node.asset_id}</p>
      <p>
        {node.asset_type} · {node.zone}
      </p>
      <p>
        Criticality: {node.criticality} · Sensitivity: {node.sensitivity}
      </p>
      <p>{node.description}</p>
      <p>Incoming: {incoming.map((item) => item.source_asset_id).join(', ') || 'none'}</p>
      <p>Outgoing: {outgoing.map((item) => item.destination_asset_id).join(', ') || 'none'}</p>
      <p>
        Observed: {state?.observed_asset_ids.includes(node.asset_id) ? 'yes' : 'no'} · Correlated:{' '}
        {state?.correlated_asset_ids.includes(node.asset_id) ? 'yes' : 'no'} · Predicted:{' '}
        {state?.predicted_asset_ids.includes(node.asset_id) ? 'hypothesis' : 'no'}
      </p>
      {liveNode ? (
        <>
          <p>
            First/latest sequence: {liveNode.first_observed_sequence ?? 'none'} /{' '}
            {liveNode.last_observed_sequence ?? 'none'} · Events: {liveNode.event_count}
          </p>
          <p>
            Latest assessment: {liveNode.classification ?? 'none'} · score{' '}
            {liveNode.anomaly_score?.toFixed(3) ?? 'none'}
          </p>
          <p>Observed techniques: {liveNode.observed_technique_ids.join(', ') || 'none'}</p>
          <p>
            Predicted target:{' '}
            {liveNode.predicted
              ? `rank ${String(liveNode.predicted_rank)} · score ${liveNode.prediction_score?.toFixed(3) ?? 'none'}`
              : 'no'}
          </p>
          {liveNode.prediction_rationale ? (
            <p className="text-xs">{liveNode.prediction_rationale}</p>
          ) : null}
        </>
      ) : null}
      <p className="text-xs text-amber-700">
        No health, availability, or confirmed compromise state is inferred.
      </p>
    </div>
  )
  if (bare)
    return (
      <>
        <p className="eyebrow">Synthetic asset</p>
        <h2 className="panel-title">{node.display_name}</h2>
        {body}
      </>
    )
  return (
    <Card>
      <CardHeader>
        <div>
          <p className="eyebrow">Synthetic asset</p>
          <h2 className="panel-title">{node.display_name}</h2>
        </div>
      </CardHeader>
      <CardContent>{body}</CardContent>
    </Card>
  )
}

export function PathInspection({
  path,
  bare = false,
}: {
  path: TopologyPath | null
  bare?: boolean
}) {
  if (!path)
    return bare ? <p className="text-slate-500">No path has been queried yet.</p> : null
  const body = (
    <>
      <p>{path.ordered_node_ids.join(' → ')}</p>
      <p>
        Length {path.path_length} · Evidence: {path.evidence_source} · Sequence:{' '}
        {path.through_sequence_number ?? 'not applicable'}
      </p>
      <p className={path.hypothetical ? 'text-amber-700' : 'text-slate-500'}>{path.statement}</p>
    </>
  )
  if (bare)
    return (
      <>
        <h2 className="panel-title capitalize">{path.path_type} path</h2>
        {body}
      </>
    )
  return (
    <Card>
      <CardHeader>
        <h2 className="panel-title">{path.path_type} path</h2>
      </CardHeader>
      <CardContent>{body}</CardContent>
    </Card>
  )
}

export function RelationshipInspector({
  edge,
  live,
  bare = false,
}: {
  edge: InfrastructureEdge | null
  live?: LiveTopologyOverlay | null
  bare?: boolean
}) {
  if (!edge)
    return bare ? <p className="text-slate-500">Select a synthetic relationship to inspect it.</p> : null
  const liveEdge = live?.edges[edge.edge_id]
  const body = (
    <>
      <p>
        {edge.source_asset_id} → {edge.destination_asset_id}
      </p>
      <p>
        {edge.relationship_type} · {edge.protocol_label ?? 'no protocol label'} · trust{' '}
        {edge.trust_level}
      </p>
      <p>
        Direction: {edge.direction} · Permitted: {edge.permitted ? 'yes' : 'no'}
      </p>
      {liveEdge ? (
        <>
          <p>
            First/latest sequence: {liveEdge.first_observed_sequence ?? 'none'} /{' '}
            {liveEdge.last_observed_sequence ?? 'none'}
          </p>
          <p>
            Events: {liveEdge.associated_event_ids.length} · Techniques:{' '}
            {liveEdge.associated_technique_ids.join(', ') || 'none'}
          </p>
          <p>
            Evidence:{' '}
            {liveEdge.anomalous_observed
              ? 'anomalous observed'
              : liveEdge.observed
                ? 'observed'
                : 'not observed'}{' '}
            · {liveEdge.correlated ? 'correlation involved' : 'not correlated'} ·{' '}
            {liveEdge.predicted ? 'hypothetical predicted path' : 'not predicted'}
          </p>
          {liveEdge.unexpected ? (
            <p className="text-amber-700">
              Unexpected observed relationship: both assets are known, but this directed edge is
              outside the expected synthetic architecture.
            </p>
          ) : null}
        </>
      ) : null}
    </>
  )
  if (bare)
    return (
      <>
        <p className="eyebrow">Synthetic relationship</p>
        <h2 className="panel-title">Relationship Inspector</h2>
        {body}
      </>
    )
  return (
    <Card>
      <CardHeader>
        <div>
          <p className="eyebrow">Synthetic relationship</p>
          <h2 className="panel-title">Relationship Inspector</h2>
        </div>
      </CardHeader>
      <CardContent>{body}</CardContent>
    </Card>
  )
}
