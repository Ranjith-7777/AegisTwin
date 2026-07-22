import { useEffect, useState } from 'react'
import { getIncidentEvidence, getRunIncidents } from '../services/correlationApi'
import { getSimulationRuns } from '../services/simulationApi'
import type { IncidentCandidate, IncidentEvidence } from '../types/correlation'
import type { SimulationRun } from '../types/simulation'
import { Card, CardContent, CardHeader } from '../components/ui/card'
import { getLatestPrediction } from '../services/predictionApi'
import type { PredictionSnapshot } from '../types/prediction'

export function IncidentsPage() {
  const [runs, setRuns] = useState<SimulationRun[]>([])
  const [runId, setRunId] = useState('')
  const [candidates, setCandidates] = useState<IncidentCandidate[]>([])
  const [selected, setSelected] = useState<IncidentCandidate | null>(null)
  const [evidence, setEvidence] = useState<IncidentEvidence[]>([])
  const [stateFilter, setStateFilter] = useState('')
  const [priorityFilter, setPriorityFilter] = useState('')
  const [prediction, setPrediction] = useState<PredictionSnapshot | null>(null)
  useEffect(() => {
    void getSimulationRuns().then(setRuns)
  }, [])
  useEffect(() => {
    if (!runId) {
      return
    }
    void getRunIncidents(runId).then((page) => {
      setCandidates(page.items)
      setSelected(page.items[0] ?? null)
    })
  }, [runId])
  useEffect(() => {
    if (!selected) {
      return
    }
    void getIncidentEvidence(selected.incident_candidate_id).then(setEvidence)
    void getLatestPrediction(selected.simulation_run_id, selected.model_id)
      .then(setPrediction)
      .catch(() => {
        setPrediction(null)
      })
  }, [selected])
  const shown = candidates.filter(
    (item) =>
      (!stateFilter || item.correlation_state === stateFilter) &&
      (!priorityFilter || item.priority === priorityFilter),
  )
  return (
    <div className="space-y-6">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Auditable synthetic evidence</p>
          <h1>Incident Candidates</h1>
          <p>Cautious correlation candidates, never confirmed incidents.</p>
        </div>
      </header>
      <Card>
        <CardHeader>
          <h2 className="panel-title">Candidate Listing</h2>
        </CardHeader>
        <CardContent>
          <label>
            Run{' '}
            <select
              aria-label="Incident candidate run"
              value={runId}
              onChange={(event) => {
                setCandidates([])
                setSelected(null)
                setEvidence([])
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
          <label className="ml-4">
            Priority{' '}
            <select
              aria-label="Candidate priority filter"
              value={priorityFilter}
              onChange={(event) => {
                setPriorityFilter(event.target.value)
              }}
              className="ml-2 bg-slate-950 p-2"
            >
              <option value="">All</option>
              <option>low</option>
              <option>medium</option>
              <option>high</option>
            </select>
          </label>
          <label className="ml-4">
            State{' '}
            <select
              aria-label="Candidate state filter"
              value={stateFilter}
              onChange={(event) => {
                setStateFilter(event.target.value)
              }}
              className="ml-2 bg-slate-950 p-2"
            >
              <option value="">All</option>
              <option>monitoring</option>
              <option>correlated</option>
              <option>high_priority</option>
              <option>closed</option>
            </select>
          </label>
          {shown.map((item) => (
            <button
              key={item.incident_candidate_id}
              className="mt-3 block w-full rounded border border-slate-800 p-3 text-left"
              onClick={() => {
                setEvidence([])
                setSelected(item)
              }}
            >
              <strong>{item.title}</strong>
              <p>
                {item.correlation_state} · {item.priority} · coherence{' '}
                {item.correlation_score.toFixed(3)} · SYNTHETIC
              </p>
            </button>
          ))}
          {shown.length === 0 ? (
            <p className="mt-3 text-slate-500">No incident candidates for this selection.</p>
          ) : null}
        </CardContent>
      </Card>
      {selected ? (
        <Card>
          <CardHeader>
            <h2 className="panel-title">Candidate Detail</h2>
          </CardHeader>
          <CardContent>
            <p>
              {selected.evidence_count} evidence items · sequence {selected.first_sequence_number}–
              {selected.latest_sequence_number}
            </p>
            <p>
              Entities: {selected.primary_user_id ?? 'none'} ·{' '}
              {selected.primary_device_id ?? 'none'}
            </p>
            <p>Assets: {selected.involved_asset_ids.join(', ')}</p>
            <p>Techniques: {selected.observed_technique_ids.join(', ')}</p>
            <h3 className="mt-4 font-semibold">Correlation Component Breakdown</h3>
            {Object.entries(selected.component_scores).map(([name, value]) => (
              <p key={name} className="text-sm">
                {name.replaceAll('_', ' ')}: {value.toFixed(3)}
              </p>
            ))}
            <h3 className="mt-4 font-semibold">Evidence Trail</h3>
            {evidence.map((item) => (
              <p key={item.evidence_id} className="mt-2 text-sm">
                Sequence {item.sequence_number}: {item.rationale}
              </p>
            ))}
            <p className="mt-4 text-xs text-amber-200">
              Correlation indicates related unusual synthetic activity. It does not confirm a real
              attack.
            </p>
            {prediction ? (
              <div className="mt-4 rounded border border-cyan-900 p-3">
                <h3 className="font-semibold">Latest predicted progression</h3>
                <p>
                  {prediction.current_stage_estimate} · through sequence{' '}
                  {prediction.through_sequence_number}
                </p>
                <p className="text-xs text-amber-200">
                  Ranked synthetic hypothesis; separate from observed incident evidence.
                </p>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
