import { useEffect, useState } from 'react'

import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { CyberDigitalTwin } from '../../components/topology/CyberDigitalTwin'
import { getTopology } from '../../services/topologyApi'
import type { CandidatePlanAssessment } from '../../types/bluePlanning'
import type { TopologySnapshot } from '../../types/topology'

/**
 * Compact What-If Digital Twin: one graph, a BEFORE / SIMULATED AFTER
 * toggle, reusing Phase 3's CyberDigitalTwin and its existing
 * "simulated-response-impact" highlight (the same one the Digital Twin
 * page's response-impact preview already uses) - never a second bespoke
 * graph renderer. Mutation ids come straight from the API's
 * CandidatePlanAssessment; nothing here is invented client-side.
 */
export function WhatIfDigitalTwin({ candidate }: { candidate: CandidatePlanAssessment }) {
  const [topology, setTopology] = useState<TopologySnapshot | null>(null)
  const [mode, setMode] = useState<'before' | 'after'>('after')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void getTopology(false)
      .then(setTopology)
      .catch(() => {
        setError('The synthetic topology is unavailable for the what-if view.')
      })
  }, [])

  const hasMutation = candidate.changed_node_ids.length > 0 || candidate.changed_edge_ids.length > 0

  return (
    <div className="mt-3 rounded border border-slate-200 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="font-semibold">What-If Digital Twin</h4>
        <Badge className="chip-warn">Hypothetical - not executed</Badge>
      </div>
      <div className="mt-2 flex gap-2" role="radiogroup" aria-label="What-if view mode">
        <Button
          size="sm"
          variant={mode === 'before' ? undefined : 'outline'}
          onClick={() => {
            setMode('before')
          }}
        >
          Before response
        </Button>
        <Button
          size="sm"
          variant={mode === 'after' ? undefined : 'outline'}
          onClick={() => {
            setMode('after')
          }}
        >
          Simulated after response
        </Button>
      </div>
      {error ? (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      ) : topology ? (
        <>
          <div style={{ height: 320 }} className="mt-2">
            <CyberDigitalTwin
              topology={topology}
              runState={null}
              variant="workspace"
              responseImpact={
                mode === 'after'
                  ? {
                      changed_node_ids: candidate.changed_node_ids,
                      changed_edge_ids: candidate.changed_edge_ids,
                    }
                  : null
              }
            />
          </div>
          <p className="mt-2 text-xs text-slate-600">
            {mode === 'after' ? (
              hasMutation ? (
                <>
                  Simulated after: {candidate.changed_edge_ids.length} relationship(s) and{' '}
                  {candidate.changed_node_ids.length} asset(s) highlighted as hypothetically
                  restricted/isolated. Remaining attack-path risk:{' '}
                  {candidate.security_gain_evidence.attack_paths_after} path(s), down from{' '}
                  {candidate.security_gain_evidence.attack_paths_before} before.
                </>
              ) : (
                'This candidate makes no connectivity change (observe-only) - before and after are identical.'
              )
            ) : (
              <>
                Before response: the real current synthetic topology, unmodified. Attack-path risk:{' '}
                {candidate.security_gain_evidence.attack_paths_before} path(s).
              </>
            )}
          </p>
        </>
      ) : (
        <p className="mt-2 text-sm">Loading synthetic topology…</p>
      )}
    </div>
  )
}
