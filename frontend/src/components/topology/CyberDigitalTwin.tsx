import { useCallback, useEffect, useMemo, useRef } from 'react'
import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  type EdgeMouseHandler,
  type NodeMouseHandler,
  type ReactFlowInstance,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { AssetNode, type AssetFlowNode, type TwinOverlay } from './AssetNode'
import { RelationshipEdge, type RelationshipFlowEdge } from './RelationshipEdge'
import { ASSET_NODE_HEIGHT, ASSET_NODE_WIDTH } from './twinGeometry'
import type {
  InfrastructureEdge,
  InfrastructureNode,
  RunTopologyState,
  TopologySnapshot,
} from '../../types/topology'
import type { LiveTopologyOverlay } from '../../types/liveTopology'
import type { ResponseImpactSimulation } from '../../types/response'
import type { SyntheticExecution } from '../../types/orchestration'

const NODE_WIDTH = ASSET_NODE_WIDTH
const NODE_HEIGHT = ASSET_NODE_HEIGHT
const COL = 180
const ROW = 140

// Four bands read top to bottom: control/identity, request path, workload and
// data, operations. The pitch leaves room for each hexagon's two label lines.
const positions: Record<string, { x: number; y: number }> = {
  'admin-service-01': { x: COL, y: 0 },
  'iam-service-01': { x: 3 * COL, y: 0 },
  'auth-pod-01': { x: 4 * COL, y: 0 },
  'external-user-01': { x: 0, y: ROW },
  'api-gateway-01': { x: COL, y: ROW },
  'load-balancer-01': { x: 2 * COL, y: ROW },
  'kubernetes-cluster-01': { x: 3 * COL, y: ROW },
  'worker-node-01': { x: 4 * COL, y: ROW },
  'object-storage-01': { x: 2 * COL, y: 2 * ROW },
  'application-pod-01': { x: 3 * COL, y: 2 * ROW },
  'cloud-database-01': { x: 4 * COL, y: 2 * ROW },
  'monitoring-service-01': { x: 3 * COL, y: 3 * ROW },
  'backup-service-01': { x: 4 * COL, y: 3 * ROW },
  'simulation-egress-sink-01': { x: 5 * COL, y: 3 * ROW },
}

/** Preview canvases use a tighter pitch so the whole estate stays legible. */
function positionOf(assetId: string, preview: boolean) {
  const base = positions[assetId] ?? { x: 0, y: 0 }
  return preview ? { x: (base.x * 150) / COL, y: (base.y * 102) / ROW } : base
}

const FIT_PADDING = 12
/** Horizontal room kept clear for the zoom controls overlay. */
const FIT_PADDING_X = 46
const FIT_MIN_ZOOM = 0.3
const FIT_MAX_ZOOM = 1.25

/** Stroke colour of each edge state, reused for its arrowhead. */
const EDGE_COLOR: Record<string, string> = {
  expected: '#c3ccd9',
  'simulation-only-external': '#c3ccd9',
  observed: '#8a99ae',
  'unexpected-observed': '#f59e0b',
  'anomalous-observed': '#f59e0b',
  correlated: '#ef4444',
  'current-focus': '#dc2626',
  predicted: '#0891b2',
  'simulated-response-impact': '#7c3aed',
  'synthetic-execution-applied': '#2563eb',
  'synthetic-rollback-restored': '#16a34a',
  'attack-path': '#ef4444',
  'attack-path-boundary': '#b91c1c',
  'blast-reachable': '#f59e0b',
  'blast-dependent': '#0891b2',
}

/** States quiet enough that a label would only add clutter. */
const UNLABELLED = new Set(['expected', 'simulation-only-external', 'observed'])

const EDGE_STATE_LABEL: Record<string, string> = {
  'unexpected-observed': 'unexpected',
  'anomalous-observed': 'anomalous',
  correlated: 'incident',
  'current-focus': 'active step',
  predicted: 'predicted',
  'simulated-response-impact': 'mitigation proposed',
  'synthetic-rollback-restored': 'restored',
}

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

export interface TwinLayers {
  observed: boolean
  correlated: boolean
  predicted: boolean
}

const ALL_LAYERS: TwinLayers = { observed: true, correlated: true, predicted: true }

function evidenceState(
  id: string,
  state: RunTopologyState | null,
  live: LiveTopologyOverlay | null,
  layers: TwinLayers,
  focusActive: boolean,
) {
  const liveNode = live?.nodes[id]
  if (liveNode?.current_focus && focusActive) return 'current-focus'
  // Incident membership is the stronger statement, so it outranks a bare anomaly.
  if (liveNode?.correlated && layers.correlated) return 'correlated'
  if (liveNode?.anomalous_observed && layers.observed) return 'anomalous-observed'
  if (liveNode?.predicted && layers.predicted) return 'predicted'
  if (liveNode?.observed && layers.observed) return 'observed'
  if (layers.predicted && state?.predicted_asset_ids.includes(id)) return 'predicted'
  if (layers.correlated && state?.correlated_asset_ids.includes(id)) return 'correlated'
  if (layers.observed && state?.observed_asset_ids.includes(id)) return 'observed'
  return 'normal'
}

/**
 * The synthetic cloud estate rendered as a graph. Three independent layers
 * are composed so they can never be confused with each other:
 *
 *  1. Evidence - observed / anomalous / correlated / predicted (from replay).
 *  2. Proposed mitigation - a what-if result, drawn as a dashed overlay ring
 *     on top of the evidence state. It is never shown as applied.
 *  3. Executed mitigation - only from a persisted synthetic execution record;
 *     replaces the node state (mitigated) or, after rollback, restored.
 */
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
  layers = ALL_LAYERS,
  selectedNodeId = null,
  showMiniMap,
  focusActive = true,
  zoneFilter = null,
}: {
  topology: TopologySnapshot
  runState: RunTopologyState | null
  /** workspace: fills its panel; preview: also tighter spacing and quiet labels. */
  variant?: 'full' | 'workspace' | 'preview'
  onSelectNode?: (node: InfrastructureNode) => void
  onSelectEdge?: (edge: InfrastructureEdge) => void
  liveOverlay?: LiveTopologyOverlay | null
  animationPaused?: boolean
  /** Proposed (what-if) mitigation. Only the changed ids are read. */
  responseImpact?: Pick<ResponseImpactSimulation, 'changed_node_ids' | 'changed_edge_ids'> | null
  /** Executed mitigation from a persisted synthetic execution record. */
  syntheticExecution?: SyntheticExecution | null
  attackPathHighlight?: AttackPathHighlight | null
  blastRadiusOverlay?: BlastRadiusOverlay | null
  layers?: TwinLayers
  selectedNodeId?: string | null
  showMiniMap?: boolean
  /** Highlight the event currently being replayed (only while the replay is live). */
  focusActive?: boolean
  /** Dim every asset outside this zone (null shows all). */
  zoneFilter?: string | null
}) {
  const compact = variant !== 'full'
  const preview = variant === 'preview'
  const executedApplied =
    syntheticExecution !== null && syntheticExecution.execution_state === 'completed_simulated'
  const executedRestored =
    syntheticExecution !== null && syntheticExecution.execution_state === 'rolled_back_simulated'
  // A proposal is only meaningful until something has actually been executed.
  const proposal = syntheticExecution ? null : responseImpact

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
        let state = evidenceState(item.asset_id, runState, liveOverlay, layers, focusActive)
        let overlay: TwinOverlay = null
        const executedHere = syntheticExecution?.changed_node_ids.includes(item.asset_id) ?? false
        if (executedHere && executedApplied) {
          state = 'synthetic-execution-applied'
          overlay = 'executed'
        } else if (executedHere && executedRestored) {
          state = 'synthetic-rollback-restored'
          overlay = 'restored'
        } else if (proposal?.changed_node_ids.includes(item.asset_id)) {
          overlay = 'proposed'
          if (state === 'normal') state = 'simulated-response-impact'
        }
        let dimmed = false
        if (attackPathHighlight) {
          if (item.asset_id === attackPathHighlight.targetAssetId) state = 'attack-path-target'
          else if (attackPathAssetSet?.has(item.asset_id)) state = 'attack-path-node'
          else dimmed = true
        } else if (zoneFilter && item.zone !== zoneFilter) {
          dimmed = true
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
          position: positionOf(item.asset_id, preview),
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
          selected: selectedNodeId === item.asset_id,
          data: {
            label: item.display_name,
            assetType: item.asset_type,
            criticality: item.criticality,
            state,
            overlay,
            dimmed,
            synthetic: true as const,
          },
        }
      }),
    [
      attackPathAssetSet,
      attackPathHighlight,
      blastRadiusOverlay,
      executedApplied,
      executedRestored,
      focusActive,
      layers,
      liveOverlay,
      proposal,
      runState,
      preview,
      selectedNodeId,
      syntheticExecution,
      topology.nodes,
      zoneFilter,
    ],
  )
  const edges = useMemo<RelationshipFlowEdge[]>(
    () =>
      topology.edges.map((item) => {
        const liveEdge = liveOverlay?.edges[item.edge_id]
        const executedHere = syntheticExecution?.changed_edge_ids.includes(item.edge_id) ?? false
        let state =
          executedHere && executedApplied
            ? 'synthetic-execution-applied'
            : executedHere && executedRestored
              ? 'synthetic-rollback-restored'
              : proposal?.changed_edge_ids.includes(item.edge_id)
                ? 'simulated-response-impact'
                : liveEdge?.current_focus && focusActive
                  ? 'current-focus'
                  : liveEdge?.correlated && layers.correlated
                    ? 'correlated'
                    : liveEdge?.anomalous_observed && layers.observed
                      ? 'anomalous-observed'
                      : liveEdge?.predicted && layers.predicted
                        ? 'predicted'
                        : liveEdge?.unexpected && layers.observed
                          ? 'unexpected-observed'
                          : liveEdge?.observed && layers.observed
                            ? 'observed'
                            : layers.predicted &&
                                runState?.predicted_edge_ids.includes(item.edge_id)
                              ? 'predicted'
                              : layers.correlated &&
                                  runState?.correlated_edge_ids.includes(item.edge_id)
                                ? 'correlated'
                                : layers.observed &&
                                    runState?.observed_edge_ids.includes(item.edge_id)
                                  ? 'observed'
                                  : item.relationship_type.includes('external')
                                    ? 'simulation-only-external'
                                    : 'expected'
        const techniques = liveEdge?.associated_technique_ids ?? []
        let label =
          compact || UNLABELLED.has(state)
            ? ''
            : (techniques[0] ?? EDGE_STATE_LABEL[state] ?? item.protocol_label ?? '')
        let dimmed = false
        const pathStep = attackPathHighlight?.steps.find((step) => step.edgeId === item.edge_id)
        if (attackPathHighlight) {
          if (pathStep) {
            state = pathStep.boundaryCrossing ? 'attack-path-boundary' : 'attack-path'
            label = `${String(pathStep.sequence)}. ${item.protocol_label ?? item.relationship_type}`
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
          } else {
            dimmed = true
          }
        }
        if (
          zoneFilter &&
          ![item.source_asset_id, item.destination_asset_id].some(
            (id) => topology.nodes.find((node) => node.asset_id === id)?.zone === zoneFilter,
          )
        )
          dimmed = true
        const markerEnd = {
          type: MarkerType.ArrowClosed,
          color: EDGE_COLOR[state] ?? '#c3ccd9',
          width: 14,
          height: 14,
        }
        return {
          id: item.edge_id,
          source: item.source_asset_id,
          target: item.destination_asset_id,
          type: 'relationship',
          data: { label, state, dimmed },
          markerEnd,
        }
      }),
    [
      attackPathHighlight,
      blastAssetSet,
      blastRadiusOverlay,
      compact,
      executedApplied,
      executedRestored,
      focusActive,
      layers,
      liveOverlay,
      proposal,
      runState,
      syntheticExecution,
      topology.edges,
      topology.nodes,
      zoneFilter,
    ],
  )
  // The library's own fit runs before the panel height is known, so the
  // viewport is computed from the declared node grid instead and re-applied
  // whenever the container resizes.
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
    const width = container.clientWidth - FIT_PADDING_X * 2
    const height = container.clientHeight - FIT_PADDING * 2
    if (width <= 0 || height <= 0) return
    const zoom = Math.min(
      FIT_MAX_ZOOM,
      Math.max(FIT_MIN_ZOOM, Math.min(width / graphWidth, height / graphHeight)),
    )
    void instance.current.setViewport({
      x: FIT_PADDING_X + (width - graphWidth * zoom) / 2 - left * zoom,
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
  const miniMap = showMiniMap ?? !compact
  return (
    <div
      ref={shell}
      className={`topology-canvas${compact ? ' is-workspace' : ''}${preview ? ' is-preview' : ''}${animationPaused ? ' animation-paused' : ''}`}
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
        elementsSelectable={Boolean(onSelectNode ?? onSelectEdge)}
        proOptions={{ hideAttribution: true }}
        minZoom={0.2}
        maxZoom={1.6}
        colorMode="light"
      >
        <Background variant={BackgroundVariant.Dots} gap={22} size={1.2} color="#d5dce6" />
        <Controls showInteractive={false} position="top-right" />
        {miniMap ? (
          <MiniMap
            pannable
            zoomable
            nodeColor="#cbd5e1"
            maskColor="rgba(241,244,249,0.7)"
            position="bottom-right"
          />
        ) : null}
      </ReactFlow>
      <div className="sr-only">
        Synthetic topology summary:{' '}
        {topology.nodes.map((node) => `${node.display_name} in ${node.zone}`).join('; ')}.
        {proposal
          ? ` A proposed mitigation would hypothetically restrict ${String(proposal.changed_node_ids.length)} nodes and ${String(proposal.changed_edge_ids.length)} links; it has not been executed.`
          : ''}
        {syntheticExecution?.execution_state === 'completed_simulated'
          ? ` An executed synthetic mitigation changed ${String(syntheticExecution.changed_node_ids.length)} nodes and ${String(syntheticExecution.changed_edge_ids.length)} links in the twin.`
          : ''}
        {executedRestored ? ' The executed mitigation was rolled back and the twin restored.' : ''}
      </div>
    </div>
  )
}
