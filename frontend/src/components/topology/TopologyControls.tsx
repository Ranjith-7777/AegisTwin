import type { DetectionModel } from '../../types/detection'
import type { SimulationRun } from '../../types/simulation'
import type { InfrastructureNode, TopologyPathType } from '../../types/topology'
import { Button } from '../ui/button'

export function TopologyControls(props: {
  nodes: InfrastructureNode[]
  runs: SimulationRun[]
  models: DetectionModel[]
  source: string
  destination: string
  pathType: TopologyPathType
  runId: string
  modelId: string
  sequence: number
  onSource: (value: string) => void
  onDestination: (value: string) => void
  onPathType: (value: TopologyPathType) => void
  onRun: (value: string) => void
  onModel: (value: string) => void
  onSequence: (value: number) => void
  onQuery: () => void
}) {
  const requiresRun = props.pathType !== 'expected'
  const requiresModel = props.pathType === 'correlated' || props.pathType === 'predicted'
  return (
    <div className="topology-query-controls">
      <select
        aria-label="Path source"
        value={props.source}
        onChange={(event) => {
          props.onSource(event.target.value)
        }}
      >
        {props.nodes.map((node) => (
          <option key={node.asset_id} value={node.asset_id}>
            {node.display_name}
          </option>
        ))}
      </select>
      <select
        aria-label="Path destination"
        value={props.destination}
        onChange={(event) => {
          props.onDestination(event.target.value)
        }}
      >
        {props.nodes.map((node) => (
          <option key={node.asset_id} value={node.asset_id}>
            {node.display_name}
          </option>
        ))}
      </select>
      <select
        aria-label="Path type"
        value={props.pathType}
        onChange={(event) => {
          props.onPathType(event.target.value as TopologyPathType)
        }}
      >
        {['expected', 'observed', 'correlated', 'predicted'].map((item) => (
          <option key={item}>{item}</option>
        ))}
      </select>
      {requiresRun ? (
        <select
          aria-label="Topology run"
          value={props.runId}
          onChange={(event) => {
            props.onRun(event.target.value)
          }}
        >
          <option value="">Select run</option>
          {props.runs.map((run) => (
            <option key={run.simulation_run_id} value={run.simulation_run_id}>
              {run.simulation_run_id.slice(0, 8)}
            </option>
          ))}
        </select>
      ) : null}
      {requiresModel ? (
        <select
          aria-label="Topology model"
          value={props.modelId}
          onChange={(event) => {
            props.onModel(event.target.value)
          }}
        >
          <option value="">Select model</option>
          {props.models.map((model) => (
            <option key={model.model_id} value={model.model_id}>
              {model.model_id.slice(0, 8)}
            </option>
          ))}
        </select>
      ) : null}
      {requiresRun ? (
        <label>
          <span>Through sequence</span>
          <input
            aria-label="Through sequence"
            type="number"
            min="1"
            value={props.sequence}
            onChange={(event) => {
              props.onSequence(event.currentTarget.valueAsNumber)
            }}
          />
        </label>
      ) : null}
      <Button
        onClick={props.onQuery}
        disabled={
          !props.source ||
          !props.destination ||
          (requiresRun && !props.runId) ||
          (requiresModel && !props.modelId)
        }
      >
        Inspect path
      </Button>
    </div>
  )
}
