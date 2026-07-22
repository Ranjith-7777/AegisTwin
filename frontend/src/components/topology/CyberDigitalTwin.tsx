import { useMemo } from 'react'
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type EdgeMouseHandler,
  type NodeMouseHandler,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { AssetNode, type AssetFlowNode } from './AssetNode'
import { RelationshipEdge, type RelationshipFlowEdge } from './RelationshipEdge'
import type {
  InfrastructureEdge,
  InfrastructureNode,
  RunTopologyState,
  TopologySnapshot,
} from '../../types/topology'
import type { LiveTopologyOverlay } from '../../types/liveTopology'

const positions: Record<string, { x: number; y: number }> = {
  'employee-laptop-01': { x: 40, y: 30 },
  'administrator-workstation-01': { x: 330, y: 30 },
  'authentication-server-01': { x: 185, y: 180 },
  'examination-portal-01': { x: 40, y: 330 },
  'application-server-01': { x: 330, y: 330 },
  'examination-database-01': { x: 185, y: 500 },
  'backup-server-01': { x: 610, y: 410 },
  'monitoring-server-01': { x: 610, y: 180 },
  'simulation-egress-sink-01': { x: 610, y: 560 },
}

function stateFor(id: string, state: RunTopologyState | null, live: LiveTopologyOverlay | null) {
  const liveNode = live?.nodes[id]
  if (liveNode?.current_focus) return 'current-focus'
  if (liveNode?.anomalous_observed) return 'anomalous-observed'
  if (liveNode?.correlated) return 'correlated'
  if (liveNode?.predicted) return 'predicted'
  if (liveNode?.observed) return 'observed'
  if (state?.predicted_asset_ids.includes(id)) return 'predicted'
  if (state?.correlated_asset_ids.includes(id)) return 'correlated'
  if (state?.observed_asset_ids.includes(id)) return 'observed'
  return 'normal'
}

export function CyberDigitalTwin({
  topology,
  runState,
  compact = false,
  onSelectNode,
  onSelectEdge,
  liveOverlay = null,
  animationPaused = false,
}: {
  topology: TopologySnapshot
  runState: RunTopologyState | null
  compact?: boolean
  onSelectNode?: (node: InfrastructureNode) => void
  onSelectEdge?: (edge: InfrastructureEdge) => void
  liveOverlay?: LiveTopologyOverlay | null
  animationPaused?: boolean
}) {
  const nodes = useMemo<AssetFlowNode[]>(
    () =>
      topology.nodes.map((item) => ({
        id: item.asset_id,
        type: 'asset',
        position: positions[item.asset_id] ?? { x: 0, y: 0 },
        data: {
          label: item.display_name,
          assetType: item.asset_type,
          criticality: item.criticality,
          state: stateFor(item.asset_id, runState, liveOverlay),
          synthetic: true,
        },
      })),
    [liveOverlay, topology.nodes, runState],
  )
  const edges = useMemo<RelationshipFlowEdge[]>(
    () =>
      topology.edges.map((item) => {
        const liveEdge = liveOverlay?.edges[item.edge_id]
        const state = liveEdge?.current_focus
          ? 'current-focus'
          : liveEdge?.anomalous_observed
            ? 'anomalous-observed'
            : liveEdge?.correlated
              ? 'correlated'
              : liveEdge?.predicted
                ? 'predicted'
                : liveEdge?.unexpected
                  ? 'unexpected-observed'
                  : liveEdge?.observed
                    ? 'observed'
                    : runState?.predicted_edge_ids.includes(item.edge_id)
                      ? 'predicted'
                      : runState?.correlated_edge_ids.includes(item.edge_id)
                        ? 'correlated'
                        : runState?.observed_edge_ids.includes(item.edge_id)
                          ? 'observed'
                          : item.relationship_type.includes('external')
                            ? 'simulation-only-external'
                            : 'expected'
        return {
          id: item.edge_id,
          source: item.source_asset_id,
          target: item.destination_asset_id,
          type: 'relationship',
          data: { label: compact ? '' : (item.protocol_label ?? item.relationship_type), state },
          animated: state === 'predicted',
        }
      }),
    [compact, liveOverlay, runState, topology.edges],
  )
  const onNodeClick: NodeMouseHandler<AssetFlowNode> = (_event, node) => {
    const asset = topology.nodes.find((item) => item.asset_id === node.id)
    if (asset) onSelectNode?.(asset)
  }
  const onEdgeClick: EdgeMouseHandler<RelationshipFlowEdge> = (_event, edge) => {
    const relationship = topology.edges.find((item) => item.edge_id === edge.id)
    if (relationship) onSelectEdge?.(relationship)
  }
  return (
    <div
      className={`${compact ? 'topology-canvas is-compact' : 'topology-canvas'}${animationPaused ? ' animation-paused' : ''}`}
      aria-label="Interactive synthetic infrastructure topology"
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={{ asset: AssetNode }}
        edgeTypes={{ relationship: RelationshipEdge }}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={!compact}
        minZoom={0.35}
        maxZoom={1.5}
      >
        <Background />
        <Controls showInteractive={false} />
        {compact ? null : <MiniMap pannable zoomable />}
      </ReactFlow>
      <div className="sr-only">
        Synthetic topology summary:{' '}
        {topology.nodes.map((node) => `${node.display_name} in ${node.zone}`).join('; ')}.
      </div>
    </div>
  )
}
