import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type Edge,
  type EdgeProps,
} from '@xyflow/react'

export interface RelationshipEdgeData extends Record<string, unknown> {
  label: string
  state: string
  dimmed?: boolean
}

export type RelationshipFlowEdge = Edge<RelationshipEdgeData, 'relationship'>

export function RelationshipEdge(props: EdgeProps<RelationshipFlowEdge>) {
  const [path, x, y] = getBezierPath(props)
  return (
    <>
      <BaseEdge
        id={props.id}
        path={path}
        markerEnd={props.markerEnd}
        className={`topology-edge state-${props.data?.state ?? 'expected'}${props.data?.dimmed ? ' dimmed' : ''}`}
      />
      <EdgeLabelRenderer>
        <span
          className="topology-edge-label"
          style={{ transform: `translate(-50%, -50%) translate(${String(x)}px,${String(y)}px)` }}
        >
          {props.data?.label}
        </span>
      </EdgeLabelRenderer>
    </>
  )
}
