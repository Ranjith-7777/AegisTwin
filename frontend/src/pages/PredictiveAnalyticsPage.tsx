import { useEffect, useState } from 'react'

import { LivePredictionDashboard } from '../components/prediction/LivePredictionDashboard'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader } from '../components/ui/card'
import { getDetectionModels } from '../services/detectionApi'
import {
  analyzePredictions,
  evaluatePredictions,
  getPredictionSnapshots,
} from '../services/predictionApi'
import { getSimulationRuns } from '../services/simulationApi'
import type { DetectionModel } from '../types/detection'
import type { PredictionEvaluation, PredictionSnapshot } from '../types/prediction'
import type { SimulationRun } from '../types/simulation'
import { getResponseSummary } from '../services/responseApi'
import type { ResponseRunSummary } from '../types/response'

export function PredictiveAnalyticsPage() {
  const [runs, setRuns] = useState<SimulationRun[]>([])
  const [models, setModels] = useState<DetectionModel[]>([])
  const [runId, setRunId] = useState('')
  const [modelId, setModelId] = useState('')
  const [snapshots, setSnapshots] = useState<PredictionSnapshot[]>([])
  const [evaluation, setEvaluation] = useState<PredictionEvaluation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [responseSummary, setResponseSummary] = useState<ResponseRunSummary | null>(null)

  useEffect(() => {
    void Promise.all([getSimulationRuns(), getDetectionModels()]).then(([runData, modelData]) => {
      setRuns(runData)
      setModels(modelData.filter((item) => item.synthetic))
    })
  }, [])

  async function load() {
    if (!runId || !modelId) return
    setBusy(true)
    setError(null)
    try {
      const page = await getPredictionSnapshots(runId, modelId)
      setSnapshots(page.items)
      setResponseSummary(await getResponseSummary(runId, modelId).catch(() => null))
    } catch {
      setError('Prediction snapshots are unavailable. Score, correlate, and analyze the run first.')
    } finally {
      setBusy(false)
    }
  }

  async function analyze() {
    if (!runId || !modelId) return
    setBusy(true)
    setError(null)
    try {
      await analyzePredictions(runId, modelId, 3, true)
      setSnapshots((await getPredictionSnapshots(runId, modelId)).items)
    } catch {
      setError('Prediction analysis requires complete scoring and correlation artifacts.')
    } finally {
      setBusy(false)
    }
  }

  async function evaluate() {
    if (!runId || !modelId) return
    setBusy(true)
    try {
      setEvaluation(await evaluatePredictions(runId, modelId))
    } catch {
      setError('Evaluation truth is available only for the staged synthetic demonstration.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Auditable local progression model</p>
          <h1>Predictive Analytics</h1>
          <p>Inspect cautious next-stage hypotheses without future-event leakage.</p>
        </div>
      </header>
      <Card>
        <CardHeader>
          <h2 className="panel-title">Analysis selection</h2>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <select
            aria-label="Prediction run"
            className="bg-slate-50 p-2"
            value={runId}
            onChange={(event) => {
              setRunId(event.target.value)
              setSnapshots([])
              setResponseSummary(null)
            }}
          >
            <option value="">Select run</option>
            {runs.map((run) => (
              <option key={run.simulation_run_id} value={run.simulation_run_id}>
                {run.simulation_run_id}
              </option>
            ))}
          </select>
          <select
            aria-label="Prediction model"
            className="bg-slate-50 p-2"
            value={modelId}
            onChange={(event) => {
              setModelId(event.target.value)
              setSnapshots([])
              setResponseSummary(null)
            }}
          >
            <option value="">Select model</option>
            {models.map((model) => (
              <option key={model.model_id} value={model.model_id}>
                {model.model_id}
              </option>
            ))}
          </select>
          <Button
            variant="outline"
            disabled={busy || !runId || !modelId}
            onClick={() => void load()}
          >
            Load snapshots
          </Button>
          <Button disabled={busy || !runId || !modelId} onClick={() => void analyze()}>
            Analyze predictions
          </Button>
          <Button
            variant="outline"
            disabled={busy || !runId || !modelId}
            onClick={() => void evaluate()}
          >
            Evaluate staged truth
          </Button>
        </CardContent>
      </Card>
      {error ? (
        <p role="alert" className="text-red-200">
          {error}
        </p>
      ) : null}
      <LivePredictionDashboard current={snapshots.at(-1) ?? null} timeline={snapshots} />
      {responseSummary?.top_recommendation ? (
        <Card>
          <CardHeader>
            <h2 className="panel-title">Separate response-analysis context</h2>
          </CardHeader>
          <CardContent>
            <p>
              Highest ranked synthetic response: {responseSummary.top_recommendation.playbook_name}
            </p>
            <p>
              Target: {responseSummary.top_recommendation.target_id} · analysis sequence{' '}
              {responseSummary.analysis_sequence}
            </p>
            <p>
              Predicted paths hypothetically interrupted:{' '}
              {responseSummary.top_recommendation.simulation?.predicted_paths_interrupted ?? 0}
            </p>
            <p className="text-xs text-amber-200">
              Prediction evidence and response simulation remain separate; no action has been
              executed.
            </p>
          </CardContent>
        </Card>
      ) : null}
      {evaluation ? (
        <Card>
          <CardHeader>
            <h2 className="panel-title">Outcome review</h2>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-amber-200">
              Tiny synthetic manifest; these metrics do not represent production performance.
            </p>
            {Object.entries(evaluation.metrics).map(([name, value]) => (
              <p key={name}>
                {name.replaceAll('_', ' ')}: {String(value)}
              </p>
            ))}
            <h3 className="mt-3 font-semibold">Baseline</h3>
            {Object.entries(evaluation.baseline_metrics).map(([name, value]) => (
              <p key={name}>
                {name.replaceAll('_', ' ')}: {String(value)}
              </p>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
