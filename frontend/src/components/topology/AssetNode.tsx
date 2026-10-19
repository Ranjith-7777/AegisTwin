import { Check, RotateCcw } from 'lucide-react'
import type { ReactElement } from 'react'
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'

import { cn } from '../../lib/utils'
import { assetIcon } from './assetIcon'

export type TwinOverlay = 'proposed' | 'executed' | 'restored' | null

export interface AssetNodeData extends Record<string, unknown> {
  label: string
  assetType: string
  criticality: string
  state: string
  overlay?: TwinOverlay
  dimmed?: boolean
  synthetic: true
}

export type AssetFlowNode = Node<AssetNodeData, 'asset'>

/** Human-readable label for each canvas state - never implies real compromise. */
const NODE_STATE_LABEL: Record<string, string> = {
  normal: 'nominal',
  observed: 'observed',
  'anomalous-observed': 'anomalous',
  correlated: 'incident evidence',
  predicted: 'predicted target',
  'current-focus': 'active attack step',
  'simulated-response-impact': 'mitigation proposed',
  'synthetic-execution-applied': 'mitigated',
  'synthetic-rollback-restored': 'restored',
  'attack-path-node': 'on attack path',
  'attack-path-target': 'path target',
  'blast-compromised': 'compromised (assumed)',
  'blast-reachable': 'reachable',
  'blast-dependent': 'dependent',
}

/** Corner badge: the strongest single fact about the node, if any. */
function badgeFor(state: string, overlay: TwinOverlay): ReactElement | null {
  if (overlay === 'executed') return <Check aria-hidden="true" strokeWidth={3} />
  if (overlay === 'restored') return <RotateCcw aria-hidden="true" strokeWidth={3} />
  if (['correlated', 'current-focus', 'attack-path-target', 'blast-compromised'].includes(state))
    return <span aria-hidden="true">!</span>
  if (state === 'anomalous-observed') return <span aria-hidden="true">!</span>
  if (state === 'predicted') return <span aria-hidden="true">?</span>
  return null
}

const HEX_POINTS = '28,2 52.2,15.5 52.2,42.5 28,56 3.8,42.5 3.8,15.5'

export function AssetNode({ data, selected }: NodeProps<AssetFlowNode>) {
  const overlay = data.overlay ?? null
  const base = NODE_STATE_LABEL[data.state] ?? data.state.replaceAll('-', ' ')
  const stateLabel =
    overlay === 'proposed' && data.state !== 'simulated-response-impact'
      ? `${base} · fix proposed`
      : base
  const badge = badgeFor(data.state, overlay)
  return (
    <div
      className={cn(
        'twin-node',
        `is-${data.criticality}`,
        `state-${data.state}`,
        overlay && `overlay-${overlay}`,
        data.dimmed && 'dimmed',
        selected && 'is-selected',
      )}
      tabIndex={0}
      aria-label={`${data.label}, ${stateLabel}, synthetic asset`}
    >
      <Handle type="target" position={Position.Top} />
      <span className="twin-hex">
        <svg className="twin-hex-shape" viewBox="0 0 56 58" aria-hidden="true">
          {overlay === 'proposed' ? (
            <polygon
              className="twin-hex-ring"
              points={HEX_POINTS}
              transform="translate(28 29) scale(1.2) translate(-28 -29)"
            />
          ) : null}
          <polygon className="twin-hex-body" points={HEX_POINTS} />
        </svg>
        <span className="twin-hex-icon">{assetIcon(data.assetType)}</span>
        {badge ? <span className="twin-badge">{badge}</span> : null}
      </span>
      <strong className="twin-node-label">{data.label}</strong>
      <span className="twin-node-state">{stateLabel}</span>
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}
