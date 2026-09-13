import { useEffect, useState } from 'react'

import { Badge } from '../../components/ui/badge'
import { Card, CardContent, CardHeader } from '../../components/ui/card'
import { getPolicyCatalogue } from '../../services/policyApi'
import type { PolicyDefinition } from '../../types/policy'

export function PoliciesPage() {
  const [policies, setPolicies] = useState<PolicyDefinition[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void getPolicyCatalogue()
      .then(setPolicies)
      .catch(() => {
        setError('The synthetic policy catalogue is unavailable.')
      })
  }, [])

  return (
    <section className="space-y-6" aria-labelledby="policies-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Blue Agent · Policies</p>
          <h1 id="policies-title">Policy-as-Code</h1>
          <p>
            A small, deterministic, inspectable policy engine - deliberately not OPA/Gatekeeper.
            Every policy decision reports a policy ID, result and reason; no boolean chain is
            hidden. The Safety Governor Agent evaluates these for every candidate plan.
          </p>
        </div>
      </header>
      {error ? (
        <p role="alert" className="text-red-700">
          {error}
        </p>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-2">
        {policies.map((policy) => (
          <Card key={policy.policy_id}>
            <CardHeader>
              <div>
                <Badge className="chip-muted">{policy.policy_id}</Badge>
                <h2 className="mt-1 font-semibold">{policy.name}</h2>
              </div>
              <Badge className={policy.enabled ? 'chip-healthy' : 'chip-muted'}>
                {policy.enabled ? 'enabled' : 'disabled'}
              </Badge>
            </CardHeader>
            <CardContent>
              <p className="text-sm">
                <strong>Purpose:</strong> {policy.purpose}
              </p>
              <p className="mt-1 text-sm">
                <strong>Applies to:</strong> {policy.applies_to}
              </p>
              <p className="mt-1 text-sm">
                <strong>Decision effect:</strong> {policy.decision_effect}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  )
}
