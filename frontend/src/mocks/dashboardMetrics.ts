import type { DashboardMetric } from '../types/dashboard'

export function getDashboardMetrics(
  activeIncidents: number,
  agentsOnline: number,
): DashboardMetric[] {
  return [
    {
      label: 'Active Incidents',
      value: String(activeIncidents),
      detail: 'Backend status',
      status: 'live',
    },
    { label: 'Global Risk Score', value: '0', detail: 'Demo Placeholder', status: 'placeholder' },
    { label: 'MTTD', value: '--', detail: 'Awaiting detection data', status: 'placeholder' },
    { label: 'MTTR', value: '--', detail: 'Awaiting response data', status: 'placeholder' },
    {
      label: 'Agents Online',
      value: String(agentsOnline),
      detail: 'Backend status',
      status: 'live',
    },
  ]
}
