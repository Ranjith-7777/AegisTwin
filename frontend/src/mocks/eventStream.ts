import type { SampleEvent } from '../types/dashboard'

export const sampleEvents: SampleEvent[] = [
  {
    id: 'SIM-0001',
    time: '09:42:10',
    message: 'Synthetic identity session started',
    severity: 'informational',
  },
  {
    id: 'SIM-0002',
    time: '09:42:24',
    message: 'Simulated endpoint heartbeat received',
    severity: 'low',
  },
  {
    id: 'SIM-0003',
    time: '09:43:02',
    message: 'Illustrative access policy check',
    severity: 'medium',
  },
]
