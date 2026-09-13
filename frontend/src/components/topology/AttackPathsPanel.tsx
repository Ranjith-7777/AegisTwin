import { useState } from 'react'

import { Card, CardContent, CardHeader } from '../ui/card'
import { Button } from '../ui/button'
import { analyzeAttackPaths } from '../../services/attackGraphApi'
import { toClientApiError } from '../../services/apiClient'
import type { AttackPathAnalysisResult, AttackPathType } from '../../types/attackGraph'
import type { InfrastructureNode } from '../../types/topology'

const PATH_TYPES: AttackPathType[] = ['potential', 'observed', 'inferred', 'predicted']

export function AttackPathsPanel({
  nodes,
  runId,
  modelId,
  sequence,
}: {
  nodes: InfrastructureNode[]
  runId: string
  modelId: string
  sequence: number
}) {
  const [source, setSource] = useState('external-user-01')
  const [target, setTarget] = useState('')
  const [pathType, setPathType] = useState<AttackPathType>('potential')
  const [result, setResult] = useState<AttackPathAnalysisResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function analyze() {
    setLoading(true)
    setError(null)
    void analyzeAttackPaths({
      sourceAssetId: source,
      targetAssetId: target || undefined,
      pathType,
      runId: pathType === 'potential' ? undefined : runId || undefined,
      modelId: pathType === 'potential' ? undefined : modelId || undefined,
      throughSequence: pathType === 'potential' ? undefined : sequence,
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
          <h2 className="panel-title">Attack Paths</h2>
          <p className="text-xs text-slate-500">
            Deterministic, ranked paths over the real synthetic topology — every score is a
            reviewable sum of graph and evidence factors, never a random or model-guessed number.
            See docs/architecture/ATTACK_GRAPH.md.
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col text-xs text-slate-600">
            Source asset
            <select
              className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
              value={source}
              onChange={(event) => {
                setSource(event.target.value)
              }}
            >
              {nodes.map((node) => (
                <option key={node.asset_id} value={node.asset_id}>
                  {node.display_name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-xs text-slate-600">
            Target asset (optional — auto-selects high-value targets)
            <select
              className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
              value={target}
              onChange={(event) => {
                setTarget(event.target.value)
              }}
            >
              <option value="">Any critical/sensitive asset</option>
              {nodes.map((node) => (
                <option key={node.asset_id} value={node.asset_id}>
                  {node.display_name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-xs text-slate-600">
            Path type
            <select
              className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
              value={pathType}
              onChange={(event) => {
                setPathType(event.target.value as AttackPathType)
              }}
            >
              {PATH_TYPES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <Button onClick={analyze} disabled={loading}>
            {loading ? 'Analyzing…' : 'Find attack paths'}
          </Button>
        </div>
        {pathType !== 'potential' && !runId ? (
          <p className="text-xs text-amber-700">
            Observed/inferred/predicted paths require a selected run — choose one in the Topology
            tab first.
          </p>
        ) : null}
        {error ? (
          <p className="text-red-700" role="alert">
            {error}
          </p>
        ) : null}
        {result ? (
          <div className="space-y-3">
            <p className="text-xs text-slate-500">
              {result.total_candidates_considered} candidate path(s) considered · showing top{' '}
              {result.paths.length}
            </p>
            {result.paths.length === 0 ? (
              <p className="text-sm text-slate-600">No attack path found for this query.</p>
            ) : null}
            {result.paths.map((path) => (
              <div key={path.path_id} className="rounded-md border border-slate-200 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="chip chip-accent">{path.path_type}</span>
                  <span className="text-sm font-semibold">
                    Priority score: {path.score.total.toFixed(1)} / 100
                  </span>
                </div>
                <p className="mt-1 text-sm text-slate-700">{path.statement}</p>
                <ol className="mt-2 space-y-1 text-xs text-slate-600">
                  {path.steps.map((step) => (
                    <li key={step.edge_id}>
                      {step.sequence}. {step.source_asset_id} → {step.destination_asset_id} (
                      {step.attack_semantics}
                      {step.privileged ? ', privileged' : ''}
                      {step.trust_boundary_crossed ? ', crosses trust boundary' : ''}) —{' '}
                      {step.reason}
                    </li>
                  ))}
                </ol>
                <p className="mt-2 text-xs text-slate-500">
                  Target criticality: {path.target_criticality} · sensitivity:{' '}
                  {path.target_sensitivity} · exposure {path.score.exposure_contribution} ·
                  privilege {path.score.privilege_contribution} · critical target{' '}
                  {path.score.critical_target_contribution} · boundary crossing{' '}
                  {path.score.boundary_crossing_contribution} · evidence{' '}
                  {path.score.evidence_contribution} · length penalty −{path.score.length_penalty}
                </p>
              </div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
