import { useCallback, useEffect, useMemo, useRef } from 'react'
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  type EdgeMouseHandler,
  type NodeMouseHandler,
  type ReactFlowInstance,
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
import type { ResponseImpactSimulation } from '../../types/response'
import type { SyntheticExecution } from '../../types/orchestration'

const NODE_WIDTH = 132
const NODE_HEIGHT = 70

// Four bands read top to bottom: control/identity, request path, workload and data,
// operations. Compact pitch keeps all thirteen nodes legible once fitted.
const positions: Record<string, { x: number; y: number }> = {
  'admin-service-01': { x: 166, y: 0 },
  'iam-service-01': { x: 498, y: 0 },
  'auth-pod-01': { x: 664, y: 0 },
  'external-user-01': { x: 0, y: 110 },
  'api-gateway-01': { x: 166, y: 110 },
  'load-balancer-01': { x: 332, y: 110 },
  'kubernetes-cluster-01': { x: 498, y: 110 },
  'worker-node-01': { x: 664, y: 110 },
  'object-storage-01': { x: 332, y: 220 },
  'application-pod-01': { x: 498, y: 220 },
  'cloud-database-01': { x: 664, y: 220 },
  'monitoring-service-01': { x: 498, y: 330 },
  'backup-service-01': { x: 664, y: 330 },
  'simulation-egress-sink-01': { x: 830, y: 330 },
}

const FIT_PADDING = 16
const FIT_MIN_ZOOM = 0.2
const FIT_MAX_ZOOM = 1.25

export interface AttackPathHighlight {
  pathType: string
  targetAssetId: string
  orderedAssetIds: string[]
  steps: { edgeId: string; sequence: number; boundaryCrossing: boolean }[]
}

export interface BlastRadiusOverlay {
  compromisedAssetIds: string[]
  reachableAssetIds: string[]
  dependentAssetIds: string[]
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
  variant = 'full',
  onSelectNode,
  onSelectEdge,
  liveOverlay = null,
  animationPaused = false,
  responseImpact = null,
  syntheticExecution = null,
  attackPathHighlight = null,
  blastRadiusOverlay = null,
}: {
  topology: TopologySnapshot
  runState: RunTopologyState | null
  variant?: 'full' | 'workspace'
  onSelectNode?: (node: InfrastructureNode) => void
  onSelectEdge?: (edge: InfrastructureEdge) => void
  liveOverlay?: LiveTopologyOverlay | null
  animationPaused?: boolean
  responseImpact?: ResponseImpactSimulation | null
  syntheticExecution?: SyntheticExecution | null
  attackPathHighlight?: AttackPathHighlight | null
  blastRadiusOverlay?: BlastRadiusOverlay | null
}) {
  const compact = variant === 'workspace'
  const attackPathAssetSet = useMemo(
    () => (attackPathHighlight ? new Set(attackPathHighlight.orderedAssetIds) : null),
    [attackPathHighlight],
  )
  const blastAssetSet = useMemo(
    () =>
      blastRadiusOverlay
        ? new Set([
            ...blastRadiusOverlay.compromisedAssetIds,
            ...blastRadiusOverlay.reachableAssetIds,
            ...blastRadiusOverlay.dependentAssetIds,
          ])
        : null,
    [blastRadiusOverlay],
  )
  const nodes = useMemo<AssetFlowNode[]>(
    () =>
      topology.nodes.map((item) => {
        let state = syntheticExecution?.changed_node_ids.includes(item.asset_id)
          ? syntheticExecution.execution_state === 'rolled_back_simulated'
            ? 'synthetic-rollback-restored'
            : 'synthetic-execution-applied'
          : responseImpact?.changed_node_ids.includes(item.asset_id)
            ? 'simulated-response-impact'
            : stateFor(item.asset_id, runState, liveOverlay)
        let dimmed = false
        if (attackPathHighlight) {
          if (item.asset_id === attackPathHighlight.targetAssetId) state = 'attack-path-target'
          else if (attackPathAssetSet?.has(item.asset_id)) state = 'attack-path-node'
          else dimmed = true
        } else if (blastRadiusOverlay) {
          if (blastRadiusOverlay.compromisedAssetIds.includes(item.asset_id)) {
            state = 'blast-compromised'
          } else if (blastRadiusOverlay.reachableAssetIds.includes(item.asset_id)) {
            state = 'blast-reachable'
          } else if (blastRadiusOverlay.dependentAssetIds.includes(item.asset_id)) {
            state = 'blast-dependent'
          } else {
            dimmed = true
          }
        }
        return {
          id: item.asset_id,
          type: 'asset' as const,
          position: positions[item.asset_id] ?? { x: 0, y: 0 },
          // Declared up front so the first fit does not wait on measurement.
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
          data: {
            label: item.display_name,
            assetType: item.asset_type,
            criticality: item.criticality,
            state,
            dimmed,
            synthetic: true as const,
          },
        }
      }),
    [
      attackPathAssetSet,
      attackPathHighlight,
      blastRadiusOverlay,
      liveOverlay,
      responseImpact,
      topology.nodes,
      runState,
      syntheticExecution,
    ],
  )
  const edges = useMemo<RelationshipFlowEdge[]>(
    () =>
      topology.edges.map((item) => {
        const liveEdge = liveOverlay?.edges[item.edge_id]
        let state = syntheticExecution?.changed_edge_ids.includes(item.edge_id)
          ? syntheticExecution.execution_state === 'rolled_back_simulated'
            ? 'synthetic-rollback-restored'
            : 'synthetic-execution-applied'
          : responseImpact?.changed_edge_ids.includes(item.edge_id)
            ? 'simulated-response-impact'
            : liveEdge?.current_focus
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
        let label = compact ? '' : (item.protocol_label ?? item.relationship_type)
        let dimmed = false
        let markerEnd: { type: MarkerType } | undefined
        const pathStep = attackPathHighlight?.steps.find((step) => step.edgeId === item.edge_id)
        if (attackPathHighlight) {
          if (pathStep) {
            state = pathStep.boundaryCrossing ? 'attack-path-boundary' : 'attack-path'
            label = `${String(pathStep.sequence)}. ${item.protocol_label ?? item.relationship_type}`
            markerEnd = { type: MarkerType.ArrowClosed }
          } else {
            dimmed = true
          }
        } else if (blastAssetSet) {
          const involved =
            blastAssetSet.has(item.source_asset_id) && blastAssetSet.has(item.destination_asset_id)
          if (involved) {
            state = blastRadiusOverlay?.dependentAssetIds.includes(item.source_asset_id)
              ? 'blast-dependent'
              : 'blast-reachable'
            markerEnd = { type: MarkerType.ArrowClosed }
          } else {
            dimmed = true
          }
        }
        return {
          id: item.edge_id,
          source: item.source_asset_id,
          target: item.destination_asset_id,
          type: 'relationship',
          data: { label, state, dimmed },
          animated: state === 'predicted',
          markerEnd,
        }
      }),
    [
      attackPathHighlight,
      blastAssetSet,
      blastRadiusOverlay,
      compact,
      liveOverlay,
      responseImpact,
      runState,
      syntheticExecution,
      topology.edges,
    ],
  )
  // The panel height is only known after layout and the library fit runs before
  // that, so the viewport is computed from the declared node grid instead and
  // re-applied whenever the container resizes.
  const shell = useRef<HTMLDivElement>(null)
  const instance = useRef<ReactFlowInstance<AssetFlowNode, RelationshipFlowEdge> | null>(null)
  const fit = useCallback(() => {
    const container = shell.current
    if (!container || !instance.current || nodes.length === 0) return
    const left = Math.min(...nodes.map((node) => node.position.x))
    const top = Math.min(...nodes.map((node) => node.position.y))
    const right = Math.max(...nodes.map((node) => node.position.x + NODE_WIDTH))
    const bottom = Math.max(...nodes.map((node) => node.position.y + NODE_HEIGHT))
    const graphWidth = Math.max(1, right - left)
    const graphHeight = Math.max(1, bottom - top)
    const width = container.clientWidth - FIT_PADDING * 2
    const height = container.clientHeight - FIT_PADDING * 2
    if (width <= 0 || height <= 0) return
    const zoom = Math.min(
      FIT_MAX_ZOOM,
      Math.max(FIT_MIN_ZOOM, Math.min(width / graphWidth, height / graphHeight)),
    )
    void instance.current.setViewport({
      x: FIT_PADDING + (width - graphWidth * zoom) / 2 - left * zoom,
      y: FIT_PADDING + (height - graphHeight * zoom) / 2 - top * zoom,
      zoom,
    })
  }, [nodes])
  useEffect(() => {
    fit()
    const container = shell.current
    if (!container || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(fit)
    observer.observe(container)
    return () => {
      observer.disconnect()
    }
  }, [fit])

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
      ref={shell}
      className={`${compact ? 'topology-canvas is-workspace' : 'topology-canvas'}${animationPaused ? ' animation-paused' : ''}`}
      aria-label="Interactive synthetic infrastructure topology"
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={{ asset: AssetNode }}
        edgeTypes={{ relationship: RelationshipEdge }}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        onInit={(item) => {
          instance.current = item
          fit()
        }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={!compact}
        proOptions={{ hideAttribution: true }}
        minZoom={0.2}
        maxZoom={1.6}
      >
        <Background gap={22} size={1} />
        <Controls showInteractive={false} position="bottom-right" />
        {compact ? null : <MiniMap pannable zoomable />}
      </ReactFlow>
      <div className="sr-only">
        Synthetic topology summary:{' '}
        {topology.nodes.map((node) => `${node.display_name} in ${node.zone}`).join('; ')}.
        {responseImpact
          ? ` Simulated response impact hypothetically restricts ${String(responseImpact.changed_node_ids.length)} nodes and ${String(responseImpact.changed_edge_ids.length)} edges; it is not an actual response.`
          : ''}
      </div>
    </div>
  )
}
