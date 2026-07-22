import { useEffect, useState } from 'react'
import { getMitreTechniques, getRunTechniques } from '../services/correlationApi'
import { getSimulationRuns } from '../services/simulationApi'
import type { MitreTechnique, TechniqueObservation } from '../types/correlation'
import type { SimulationRun } from '../types/simulation'
import { Card, CardContent, CardHeader } from '../components/ui/card'
import { getLatestPrediction } from '../services/predictionApi'
import type { PredictionSnapshot } from '../types/prediction'

export function MitrePage() {
  const [catalogue, setCatalogue] = useState<MitreTechnique[]>([])
  const [runs, setRuns] = useState<SimulationRun[]>([])
  const [runId, setRunId] = useState('')
  const [observations, setObservations] = useState<TechniqueObservation[]>([])
  const [error, setError] = useState<string | null>(null)
  const [prediction, setPrediction] = useState<PredictionSnapshot | null>(null)
  useEffect(() => {
    void Promise.all([getMitreTechniques(), getSimulationRuns()])
      .then(([techniques, runItems]) => {
        setCatalogue(techniques)
        setRuns(runItems)
      })
      .catch(() => {
        setError('Synthetic MITRE data is unavailable.')
      })
  }, [])
  useEffect(() => {
    if (!runId) {
      return
    }
    void getRunTechniques(runId)
      .then((page) => {
        setObservations(page.items)
        const modelId = page.items[0]?.model_id
        if (modelId) {
          void getLatestPrediction(runId, modelId)
            .then(setPrediction)
            .catch(() => {
              setPrediction(null)
            })
        }
      })
      .catch(() => {
        setError('Technique observations are unavailable.')
      })
  }, [runId])
  return (
    <div className="space-y-6">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Local curated catalogue</p>
          <h1>MITRE ATT&CK Observations</h1>
          <p>Catalogue coverage and evidence-based observations remain distinct and synthetic.</p>
        </div>
      </header>
      {error ? <p role="alert">{error}</p> : null}
      <Card>
        <CardHeader>
          <h2 className="panel-title">Catalogue Techniques</h2>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          {catalogue.map((item) => (
            <article
              key={item.technique_id}
              className="rounded border border-slate-800 p-3 text-sm"
            >
              <strong>
                {item.technique_id} — {item.name}
              </strong>
              <p className="text-slate-400">{item.tactics.join(', ')}</p>
              <p>{item.description}</p>
              <p className="mt-2 text-xs text-slate-500">Requires: {item.mapping_conditions}</p>
            </article>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <h2 className="panel-title">Observed Techniques by Run</h2>
        </CardHeader>
        <CardContent>
          <label>
            Run{' '}
            <select
              aria-label="MITRE observation run"
              value={runId}
              onChange={(event) => {
                setObservations([])
                setRunId(event.target.value)
              }}
              className="ml-2 bg-slate-950 p-2"
            >
              <option value="">Select run</option>
              {runs.map((run) => (
                <option key={run.simulation_run_id} value={run.simulation_run_id}>
                  {run.simulation_run_id}
                </option>
              ))}
            </select>
          </label>
          {observations.length ? (
            <ol className="mt-4 space-y-2">
              {observations.map((item) => (
                <li key={item.mapping_id}>
                  {item.technique_id} · {item.tactic} · sequence {item.sequence_number}:{' '}
                  {item.rationale}
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-3 text-slate-500">
              No persisted mappings for the selected run. Unsupported or unmapped events are not
              assigned techniques.
            </p>
          )}
          {prediction ? (
            <div className="mt-4 rounded border border-cyan-900 p-3">
              <strong>Predicted, not observed</strong>
              <p>
                {prediction.hypotheses
                  .filter((item) => item.hypothesis_type === 'next_technique')
                  .map(
                    (item) => `#${String(item.rank)} ${item.predicted_technique_id ?? 'unknown'}`,
                  )
                  .join(' · ')}
              </p>
              <p className="text-xs text-amber-200">
                Cautious synthetic rankings remain separate from the observed timeline above.
              </p>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
