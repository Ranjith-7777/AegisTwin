export type Severity = 'informational' | 'low' | 'medium' | 'high' | 'critical'

export interface DashboardMetric {
  label: string
  value: string
  detail: string
  status: 'live' | 'placeholder'
}

export interface SampleEvent {
  id: string
  time: string
  message: string
  severity: Severity
}

export interface ThreatActivityPoint {
  time: string
  activity: number
}
