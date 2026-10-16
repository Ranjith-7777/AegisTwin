import {
  BaseEdge,
  EdgeLabelRenderer,
  getStraightPath,
  useInternalNode,
  type Edge,
  type EdgeProps,
  type InternalNode,
} from '@xyflow/react'

import { ASSET_NODE_WIDTH, HEX_CENTER_Y, HEX_RADIUS } from './twinGeometry'

export interface RelationshipEdgeData extends Record<string, unknown> {
  label: string
  state: string
  dimmed?: boolean
}

export type RelationshipFlowEdge = Edge<RelationshipEdgeData, 'relationship'>

/** Centre of the node's hexagon (not of its whole box, which includes the labels). */
function hexCenter(node: InternalNode) {
  const width = node.measured.width ?? ASSET_NODE_WIDTH
  return {
    x: node.internals.positionAbsolute.x + width / 2,
    y: node.internals.positionAbsolute.y + HEX_CENTER_Y,
  }
}

/** Point `distance` from `from` along the segment towards `to`. */
function along(
  from: { x: number; y: number },
  to: { x: number; y: number },
  distance: number,
): { x: number; y: number } {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const length = Math.hypot(dx, dy) || 1
  return { x: from.x + (dx / length) * distance, y: from.y + (dy / length) * distance }
}

/**
 * Straight "floating" relationship edge drawn hexagon-centre to
 * hexagon-centre and clipped just outside each hexagon, so the network reads
 * cleanly wherever the nodes sit.
 */
export function RelationshipEdge(props: EdgeProps<RelationshipFlowEdge>) {
  const source = useInternalNode(props.source)
  const target = useInternalNode(props.target)
  if (!source || !target) return null
  const from = hexCenter(source)
  const to = hexCenter(target)
  const start = along(from, to, HEX_RADIUS + 3)
  const end = along(to, from, HEX_RADIUS + 5)
  const [path, labelX, labelY] = getStraightPath({
    sourceX: start.x,
    sourceY: start.y,
    targetX: end.x,
    targetY: end.y,
  })
  const state = props.data?.state ?? 'expected'
  return (
    <>
      <BaseEdge
        id={props.id}
        path={path}
        markerEnd={props.markerEnd}
        className={`topology-edge state-${state}${props.data?.dimmed ? ' dimmed' : ''}`}
      />
      {state === 'synthetic-execution-applied' ? (
        <EdgeLabelRenderer>
          <span
            className="topology-edge-cut"
            title="Relationship severed by the executed synthetic mitigation"
            style={{
              transform: `translate(-50%, -50%) translate(${String(labelX)}px,${String(labelY)}px)`,
            }}
          >
            ×
          </span>
        </EdgeLabelRenderer>
      ) : props.data?.label ? (
        <EdgeLabelRenderer>
          <span
            className={`topology-edge-label state-${state}`}
            style={{
              transform: `translate(-50%, -50%) translate(${String(labelX)}px,${String(labelY)}px)`,
            }}
          >
            {props.data.label}
          </span>
        </EdgeLabelRenderer>
      ) : null}
    </>
  )
}
