import { ShieldCheck } from 'lucide-react'
import { PlaceholderPage } from './PlaceholderPage'
export function MitrePage() {
  return (
    <PlaceholderPage
      title="MITRE ATT&CK"
      phase="Phase 5"
      description="Evidence-backed mappings from simulated incident activity."
      icon={ShieldCheck}
    />
  )
}
