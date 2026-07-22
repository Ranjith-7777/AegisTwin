import type {
  InfrastructureEdge,
  InfrastructureNode,
  RunTopologyState,
  TopologyPath,
} from '../../types/topology'
import { Card, CardContent, CardHeader } from '../ui/card'

export function ZoneGroup() {
  return (
    <p className="text-xs text-slate-400">
      Zones: User → Identity → Application → Data · Operations adjacent · Synthetic External
      isolated
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
}: {
  node: InfrastructureNode | null
  edges: InfrastructureEdge[]
  state: RunTopologyState | null
}) {
  if (!node)
    return (
      <Card>
        <CardHeader>
          <h2 className="panel-title">Asset Inspector</h2>
        </CardHeader>
        <CardContent>
          <p className="text-slate-500">Select a synthetic asset to inspect it.</p>
        </CardContent>
      </Card>
    )
  const incoming = edges.filter((edge) => edge.destination_asset_id === node.asset_id)
  const outgoing = edges.filter((edge) => edge.source_asset_id === node.asset_id)
  return (
    <Card>
      <CardHeader>
        <div>
          <p className="eyebrow">SYNTHETIC ASSET</p>
          <h2 className="panel-title">{node.display_name}</h2>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
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
        <p className="text-xs text-amber-200">
          No health, availability, or confirmed compromise state is inferred.
        </p>
      </CardContent>
    </Card>
  )
}

export function PathInspection({ path }: { path: TopologyPath | null }) {
  if (!path) return null
  return (
    <Card>
      <CardHeader>
        <h2 className="panel-title">{path.path_type} path</h2>
      </CardHeader>
      <CardContent>
        <p>{path.ordered_node_ids.join(' → ')}</p>
        <p>
          Length {path.path_length} · Evidence: {path.evidence_source} · Sequence:{' '}
          {path.through_sequence_number ?? 'not applicable'}
        </p>
        <p className={path.hypothetical ? 'text-amber-200' : 'text-slate-400'}>{path.statement}</p>
      </CardContent>
    </Card>
  )
}

export function RelationshipInspector({ edge }: { edge: InfrastructureEdge | null }) {
  if (!edge) return null
  return (
    <Card>
      <CardHeader>
        <div>
          <p className="eyebrow">SYNTHETIC RELATIONSHIP</p>
          <h2 className="panel-title">Relationship Inspector</h2>
        </div>
      </CardHeader>
      <CardContent>
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
      </CardContent>
    </Card>
  )
}
