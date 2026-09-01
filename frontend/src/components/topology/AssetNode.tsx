import { Database, HardDrive, Laptop, Server, ShieldCheck } from 'lucide-react'
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'

import { cn } from '../../lib/utils'

export interface AssetNodeData extends Record<string, unknown> {
  label: string
  assetType: string
  criticality: string
  state: string
  synthetic: true
}

export type AssetFlowNode = Node<AssetNodeData, 'asset'>

export function AssetNode({ data, selected }: NodeProps<AssetFlowNode>) {
  const Icon =
    data.assetType === 'endpoint'
      ? Laptop
      : data.assetType === 'database'
        ? Database
        : data.assetType.includes('identity')
          ? ShieldCheck
          : data.assetType.includes('backup')
            ? HardDrive
            : Server
  return (
    <div
      className={cn(
        'topology-asset-node',
        `is-${data.criticality}`,
        `state-${data.state}`,
        selected && 'is-selected',
      )}
      tabIndex={0}
      aria-label={`${data.label}, ${data.state}, synthetic asset`}
    >
      <Handle type="target" position={Position.Top} />
      <Icon className="size-4" aria-hidden="true" />
      <strong>{data.label}</strong>
      <span>{data.state}</span>
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}
