import { Card, CardContent, CardHeader } from '../../components/ui/card'
import type { useBlueAgentSelection } from './useBlueAgentSelection'

/** Shared run/model/incident/sequence picker rendered atop every Blue Agent tab. */
export function IncidentContextSelector(props: ReturnType<typeof useBlueAgentSelection>) {
  const { runs, models, candidates, runId, modelId, candidateId, sequence } = props
  return (
    <Card>
      <CardHeader>
        <h2 className="panel-title">Incident context</h2>
      </CardHeader>
      <CardContent className="flex flex-wrap items-end gap-3">
        <label>
          Run
          <select
            aria-label="Blue Agent run"
            value={runId}
            onChange={(event) => {
              props.setRunId(event.target.value)
            }}
            className="mt-1 block bg-slate-50 p-2"
          >
            <option value="">Select run</option>
            {runs.map((run) => (
              <option key={run.simulation_run_id} value={run.simulation_run_id}>
                {run.simulation_run_id.slice(0, 8)} · {run.scenario_id}
              </option>
            ))}
          </select>
        </label>
        <label>
          Model
          <select
            aria-label="Blue Agent model"
            value={modelId}
            onChange={(event) => {
              props.setModelId(event.target.value)
            }}
            className="mt-1 block bg-slate-50 p-2"
          >
            <option value="">Select model</option>
            {models.map((model) => (
              <option key={model.model_id} value={model.model_id}>
                {model.model_id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Incident
          <select
            aria-label="Blue Agent incident candidate"
            value={candidateId}
            disabled={!runId}
            onChange={(event) => {
              props.setCandidateId(event.target.value)
            }}
            className="mt-1 block bg-slate-50 p-2"
          >
            <option value="">Select incident</option>
            {candidates.map((candidate) => (
              <option key={candidate.incident_candidate_id} value={candidate.incident_candidate_id}>
                {candidate.title} ({candidate.priority})
              </option>
            ))}
          </select>
        </label>
        <label>
          Through sequence
          <input
            aria-label="Blue Agent through sequence"
            type="number"
            min={1}
            value={sequence || ''}
            onChange={(event) => {
              props.setSequence(Number(event.target.value))
            }}
            className="mt-1 block w-28 bg-slate-50 p-2"
          />
        </label>
      </CardContent>
    </Card>
  )
}
