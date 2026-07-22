import { useEffect, useRef, useState } from 'react'

import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader } from '../components/ui/card'
import { getDetectionModels } from '../services/detectionApi'
import { analyzeResponses, getResponsePlaybooks } from '../services/responseApi'
import { getSimulationRuns } from '../services/simulationApi'
import type { DetectionModel } from '../types/detection'
import type {
  DefensivePlaybook,
  ResponseAnalysisResult,
  ResponseRecommendation,
} from '../types/response'
import type { SimulationRun } from '../types/simulation'

function label(value: string) {
  return value.replaceAll('_', ' ')
}

export function ResponseCentrePage() {
  const [runs, setRuns] = useState<SimulationRun[]>([])
  const [models, setModels] = useState<DetectionModel[]>([])
  const [playbooks, setPlaybooks] = useState<DefensivePlaybook[]>([])
  const [runId, setRunId] = useState('')
  const [modelId, setModelId] = useState('')
  const [sequence, setSequence] = useState(1)
  const [predictionEnabled, setPredictionEnabled] = useState(true)
  const [analysis, setAnalysis] = useState<ResponseAnalysisResult | null>(null)
  const [selected, setSelected] = useState<ResponseRecommendation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const errorRef = useRef<HTMLParagraphElement>(null)

  useEffect(() => {
    void Promise.all([getSimulationRuns(), getDetectionModels(), getResponsePlaybooks()])
      .then(([runItems, modelItems, catalogue]) => {
        setRuns(runItems)
        setModels(modelItems.filter((item) => item.synthetic))
        setPlaybooks(catalogue)
      })
      .catch(() => {
        setError('Synthetic response prerequisites are unavailable.')
      })
  }, [])
  useEffect(() => {
    if (error) errorRef.current?.focus()
  }, [error])

  function clearAnalysis() {
    setAnalysis(null)
    setSelected(null)
    setError(null)
  }

  async function analyze() {
    if (!runId || !modelId) return
    setBusy(true)
    setError(null)
    try {
      const result = await analyzeResponses({
        runId,
        modelId,
        throughSequence: sequence,
        predictionEnabled,
        topK: 5,
      })
      setAnalysis(result)
      setSelected(result.recommendations[0] ?? null)
    } catch (reason) {
      setAnalysis(null)
      setSelected(null)
      setError(reason instanceof Error ? reason.message : 'Synthetic response analysis failed.')
    } finally {
      setBusy(false)
    }
  }

  const playbook = selected
    ? playbooks.find((item) => item.playbook_id === selected.playbook_id)
    : null
  return (
    <div className="space-y-6">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Decision support · synthetic only</p>
          <h1>Response Centre</h1>
          <p>Rank defensive options and simulate their impact on a cloned digital twin.</p>
        </div>
      </header>
      <p className="rounded border border-amber-800 bg-amber-950/30 p-3 text-sm text-amber-100">
        Recommendations are generated and evaluated only against the synthetic digital twin. No real
        defensive action has been executed.
      </p>
      <Card>
        <CardHeader>
          <h2 className="panel-title">Causal response analysis</h2>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3">
          <label>
            Run
            <select
              aria-label="Response run"
              value={runId}
              onChange={(event) => {
                setRunId(event.target.value)
                setSequence(
                  runs.find((item) => item.simulation_run_id === event.target.value)?.event_count ??
                    1,
                )
                clearAnalysis()
              }}
              className="mt-1 block bg-slate-950 p-2"
            >
              <option value="">Select run</option>
              {runs.map((run) => (
                <option key={run.simulation_run_id} value={run.simulation_run_id}>
                  {run.simulation_run_id}
                </option>
              ))}
            </select>
          </label>
          <label>
            Model
            <select
              aria-label="Response model"
              value={modelId}
              onChange={(event) => {
                setModelId(event.target.value)
                clearAnalysis()
              }}
              className="mt-1 block bg-slate-950 p-2"
            >
              <option value="">Select model</option>
              {models.map((model) => (
                <option key={model.model_id} value={model.model_id}>
                  {model.model_id}
                </option>
              ))}
            </select>
          </label>
          <label>
            Through sequence
            <input
              aria-label="Response through sequence"
              type="number"
              min={1}
              value={sequence}
              onChange={(event) => {
                setSequence(Number(event.target.value))
                clearAnalysis()
              }}
              className="mt-1 block w-28 bg-slate-950 p-2"
            />
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={predictionEnabled}
              onChange={(event) => {
                setPredictionEnabled(event.target.checked)
                clearAnalysis()
              }}
            />
            Use prediction evidence
          </label>
          <Button disabled={busy || !runId || !modelId} onClick={() => void analyze()}>
            {busy ? 'Analyzing…' : 'Analyze Synthetic Responses'}
          </Button>
        </CardContent>
      </Card>
      {error ? (
        <p ref={errorRef} tabIndex={-1} role="alert" className="text-red-200">
          {error}
        </p>
      ) : null}
      {!analysis && !error ? (
        <Card>
          <CardContent>
            <p>
              No response analysis selected. Prepare detection and correlation, then analyze a
              causal sequence.
            </p>
          </CardContent>
        </Card>
      ) : null}
      {analysis ? (
        <div className="grid gap-4 lg:grid-cols-2" aria-label="Ranked synthetic recommendations">
          {analysis.recommendations.map((item) => (
            <button
              key={item.recommendation_id}
              className={`rounded border p-4 text-left ${selected?.recommendation_id === item.recommendation_id ? 'border-cyan-400' : 'border-slate-800'}`}
              onClick={() => {
                setSelected(item)
              }}
            >
              <span className="text-xs text-cyan-300">RANK {item.rank} · SYNTHETIC</span>
              <h2 className="font-semibold">{item.playbook_name}</h2>
              <p>
                {item.target_type}: {item.target_id}
              </p>
              <p>Relative recommendation score: {item.recommendation_score.toFixed(3)}</p>
              <p>
                Approval: {label(item.required_approval_tier)} ·{' '}
                {item.simulation?.reversibility ?? 'unknown'} ·{' '}
                {item.simulation?.blast_radius ?? 'unknown'} blast radius
              </p>
              <p>
                Correlated paths interrupted: {item.simulation?.correlated_paths_interrupted ?? 0} ·
                Predicted paths interrupted: {item.simulation?.predicted_paths_interrupted ?? 0}
              </p>
            </button>
          ))}
        </div>
      ) : null}
      {selected?.simulation ? (
        <>
          <Card>
            <CardHeader>
              <h2 className="panel-title">Recommendation evidence and policy</h2>
            </CardHeader>
            <CardContent>
              <p>
                <strong>{playbook?.description}</strong>
              </p>
              {selected.evidence_summary.map((item) => (
                <p key={item}>{item}</p>
              ))}
              <p className="mt-2">{selected.rationale}</p>
              <h3 className="mt-3 font-semibold">Component-score breakdown</h3>
              {Object.entries(selected.component_scores).map(([name, value]) => (
                <p key={name}>
                  {label(name)}: {value.toFixed(3)}
                </p>
              ))}
              <h3 className="mt-3 font-semibold">Penalties</h3>
              {Object.entries(selected.penalties).map(([name, value]) => (
                <p key={name}>
                  {label(name)}: {value.toFixed(3)}
                </p>
              ))}
              <div role="status" className="mt-3 text-amber-200">
                {[...selected.warnings, ...selected.simulation.warnings].map((item) => (
                  <p key={item}>{item}</p>
                ))}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <h2 className="panel-title">Baseline versus simulated topology</h2>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded border border-slate-700 p-3">
                  <h3>Baseline synthetic topology</h3>
                  <p>
                    Sensitive assets reachable:{' '}
                    {selected.simulation.sensitive_assets_reachable_before}
                  </p>
                  <p>Paths represented: {selected.simulation.paths_before.length}</p>
                </div>
                <div className="rounded border border-cyan-800 p-3">
                  <h3>Simulated post-response topology</h3>
                  <p>
                    Hypothetically restricted nodes:{' '}
                    {selected.simulation.changed_node_ids.join(', ') || 'none'}
                  </p>
                  <p>
                    Hypothetically restricted edges:{' '}
                    {selected.simulation.changed_edge_ids.join(', ') || 'none'}
                  </p>
                  <p>
                    Sensitive assets reachable:{' '}
                    {selected.simulation.sensitive_assets_reachable_after}
                  </p>
                  <p>
                    Expected business paths affected:{' '}
                    {selected.simulation.expected_relationships_affected}
                  </p>
                </div>
              </div>
              <p className="mt-3" aria-label="Impact simulation textual summary">
                Relative interruption {selected.simulation.interruption_score.toFixed(3)} · residual
                exposure {selected.simulation.residual_exposure_score.toFixed(3)} · operational
                disruption {selected.simulation.operational_disruption_score.toFixed(3)}. These are
                heuristic simulation measures, not probabilities.
              </p>
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  )
}
