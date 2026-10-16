import {
  Boxes,
  Cloud,
  Container,
  Database,
  Gauge,
  HardDrive,
  KeyRound,
  Laptop,
  Network,
  Server,
  ShieldCheck,
  Waypoints,
} from 'lucide-react'
import type { ReactElement } from 'react'

/** Icon for a synthetic asset type, shared by the twin canvas and inspectors. */
export function assetIcon(assetType: string): ReactElement {
  const props = { 'aria-hidden': true, strokeWidth: 2 } as const
  if (assetType.includes('sink')) return <Cloud {...props} />
  if (assetType === 'kubernetes_node') return <Server {...props} />
  if (assetType === 'endpoint' || assetType.includes('external')) return <Laptop {...props} />
  if (assetType.includes('database')) return <Database {...props} />
  if (assetType.includes('object_storage') || assetType.includes('storage'))
    return <Cloud {...props} />
  if (assetType.includes('identity') || assetType.includes('iam')) return <KeyRound {...props} />
  if (assetType.includes('auth')) return <ShieldCheck {...props} />
  if (assetType.includes('backup')) return <HardDrive {...props} />
  if (assetType.includes('gateway')) return <Waypoints {...props} />
  if (assetType.includes('load_balancer')) return <Network {...props} />
  if (assetType.includes('pod')) return <Container {...props} />
  if (assetType.includes('cluster') || assetType.includes('kubernetes')) return <Boxes {...props} />
  if (assetType.includes('monitoring')) return <Gauge {...props} />
  return <Server {...props} />
}
