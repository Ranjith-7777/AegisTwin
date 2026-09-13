import { useState } from 'react'

import { Card, CardContent, CardHeader } from '../ui/card'
import { Button } from '../ui/button'
import { estimateBlastRadius } from '../../services/blastRadiusApi'
import { toClientApiError } from '../../services/apiClient'
import type { BlastRadiusResult } from '../../types/blastRadius'
import type { InfrastructureNode } from '../../types/topology'

export function BlastRadiusPanel({
  nodes,
  runId,
  sequence,
}: {
  nodes: InfrastructureNode[]
  runId: string
  sequence: number
}) {
  const [compromised, setCompromised] = useState<string[]>(['auth-pod-01'])
  const [result, setResult] = useState<BlastRadiusResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function toggle(assetId: string) {
    setCompromised((current) =>
      current.includes(assetId)
        ? current.filter((item) => item !== assetId)
        : [...current, assetId],
    )
  }

  function estimate() {
    if (compromised.length === 0) {
      setError('Select at least one compromised asset.')
      return
    }
    setLoading(true)
    setError(null)
    void estimateBlastRadius({
      compromisedAssetIds: compromised,
      runId: runId || undefined,
      throughSequence: runId ? sequence : undefined,
    })
      .then(setResult)
      .catch((cause: unknown) => {
        setResult(null)
        setError(toClientApiError(cause).message)
      })
      .finally(() => {
        setLoading(false)
      })
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <h2 className="panel-title">Blast Radius</h2>
          <p className="text-xs text-slate-500">
            A conservative, worst-case estimate over the full permitted static graph — not a claim
            of what has already happened. See docs/architecture/BLAST_RADIUS.md.
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-xs text-slate-600">Compromised asset(s)</p>
          <div className="mt-1 flex flex-wrap gap-2">
            {nodes.map((node) => (
              <label
                key={node.asset_id}
                className="flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-xs"
              >
                <input
                  type="checkbox"
                  checked={compromised.includes(node.asset_id)}
                  onChange={() => {
                    toggle(node.asset_id)
                  }}
                />
                {node.display_name}
              </label>
            ))}
          </div>
        </div>
        <Button onClick={estimate} disabled={loading}>
          {loading ? 'Estimating…' : 'Estimate blast radius'}
        </Button>
        {error ? (
          <p className="text-red-700" role="alert">
            {error}
          </p>
        ) : null}
        {result ? (
          <div className="space-y-3">
            <p className="text-sm text-slate-700">{result.statement}</p>
            <div className="playback-facts">
              <div>
                <span>Reachable</span>
                <strong>{result.reachable_count}</strong>
              </div>
              <div>
                <span>Dependent</span>
                <strong>{result.dependent_count}</strong>
              </div>
              <div>
                <span>Critical at risk</span>
                <strong>{result.critical_count}</strong>
              </div>
              <div>
                <span>Score</span>
                <strong>{result.score.total.toFixed(1)} / 100</strong>
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <p className="text-xs font-semibold text-slate-600">Reachable assets</p>
                <p className="text-xs text-slate-500">
                  {result.reachable_asset_ids.join(', ') || '—'}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-600">Dependent assets</p>
                <p className="text-xs text-slate-500">
                  {result.dependent_asset_ids.join(', ') || '—'}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-600">Critical assets at risk</p>
                <p className="text-xs text-slate-500">
                  {result.critical_assets_at_risk.join(', ') || '—'}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-600">Trust zones reached</p>
                <p className="text-xs text-slate-500">
                  {result.trust_zones_reached.join(', ') || '—'}
                </p>
              </div>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
