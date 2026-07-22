import { useEffect, useMemo, useState } from 'react'

import { CyberDigitalTwin } from '../components/topology/CyberDigitalTwin'
import { TopologyControls } from '../components/topology/TopologyControls'
import {
  AssetInspector,
  PathInspection,
  PathLegend,
  RelationshipInspector,
  TopologyStatusSummary,
  ZoneGroup,
} from '../components/topology/TopologyPanels'
import { Card, CardContent, CardHeader } from '../components/ui/card'
import { useTopology } from '../hooks/useTopology'
import { getDetectionModels } from '../services/detectionApi'
import { getSimulationRuns } from '../services/simulationApi'
import type { DetectionModel } from '../types/detection'
import type { SimulationRun } from '../types/simulation'
import type { TopologyPathType } from '../types/topology'

export function DigitalTwinPage() {
  const topologyState = useTopology()
  const [runs, setRuns] = useState<SimulationRun[]>([])
  const [models, setModels] = useState<DetectionModel[]>([])
  const [source, setSource] = useState('employee-laptop-01')
  const [destination, setDestination] = useState('examination-database-01')
  const [pathType, setPathType] = useState<TopologyPathType>('expected')
  const [runId, setRunId] = useState('')
  const [modelId, setModelId] = useState('')
  const [sequence, setSequence] = useState(1)
  const [layers, setLayers] = useState({ observed: true, correlated: true, predicted: true })
  const visibleRunState = useMemo(() => {
    const state = topologyState.runState
    if (!state) return null
    return {
      ...state,
      observed_asset_ids: layers.observed ? state.observed_asset_ids : [],
      observed_edge_ids: layers.observed ? state.observed_edge_ids : [],
      correlated_asset_ids: layers.correlated ? state.correlated_asset_ids : [],
      correlated_edge_ids: layers.correlated ? state.correlated_edge_ids : [],
      predicted_asset_ids: layers.predicted ? state.predicted_asset_ids : [],
      predicted_edge_ids: layers.predicted ? state.predicted_edge_ids : [],
    }
  }, [layers, topologyState.runState])

  useEffect(() => {
    void Promise.all([getSimulationRuns(), getDetectionModels()])
      .then(([runItems, modelItems]) => {
        setRuns(runItems)
        setModels(modelItems.filter((item) => item.synthetic))
      })
      .catch(() => undefined)
  }, [])

  function changeRun(value: string) {
    setRunId(value)
    setModelId('')
    setSequence(1)
    if (value) void topologyState.loadRunState(value, undefined, 1)
  }

  function query() {
    void topologyState.queryPath({
      source,
      destination,
      pathType,
      runId: runId || undefined,
      modelId: modelId || undefined,
      throughSequence: pathType === 'expected' ? undefined : sequence,
    })
    if (runId) void topologyState.loadRunState(runId, modelId || undefined, sequence)
  }

  return (
    <div className="space-y-6">
      <header className="page-heading">
        <div>
          <p className="eyebrow">INTERACTIVE · SYNTHETIC ONLY</p>
          <h1>Cyber Digital Twin</h1>
          <p>Inspect the repository-defined infrastructure and sequence-bounded path evidence.</p>
        </div>
      </header>
      {topologyState.error ? (
        <p className="text-red-200" role="alert">
          {topologyState.error}
        </p>
      ) : null}
      {topologyState.loading ? <p>Loading synthetic topology…</p> : null}
      {topologyState.topology ? (
        <>
          <TopologyStatusSummary
            version={topologyState.topology.topology_version}
            nodeCount={topologyState.topology.nodes.length}
            edgeCount={topologyState.topology.edges.length}
          />
          <Card>
            <CardHeader>
              <h2 className="panel-title">Topology and path controls</h2>
            </CardHeader>
            <CardContent className="space-y-3">
              <ZoneGroup />
              <PathLegend />
              <div className="flex flex-wrap gap-4" aria-label="Visible topology layers">
                {(['observed', 'correlated', 'predicted'] as const).map((layer) => (
                  <label key={layer} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={layers[layer]}
                      onChange={(event) => {
                        setLayers((current) => ({ ...current, [layer]: event.target.checked }))
                      }}
                    />
                    {layer} layer
                  </label>
                ))}
              </div>
              <TopologyControls
                nodes={topologyState.topology.nodes}
                runs={runs}
                models={models}
                source={source}
                destination={destination}
                pathType={pathType}
                runId={runId}
                modelId={modelId}
                sequence={sequence}
                onSource={setSource}
                onDestination={setDestination}
                onPathType={setPathType}
                onRun={changeRun}
                onModel={setModelId}
                onSequence={setSequence}
                onQuery={query}
              />
            </CardContent>
          </Card>
          <CyberDigitalTwin
            topology={topologyState.topology}
            runState={visibleRunState}
            onSelectNode={topologyState.selectNode}
            onSelectEdge={topologyState.selectEdge}
          />
          <div className="grid gap-6 lg:grid-cols-2">
            <AssetInspector
              node={topologyState.selectedNode}
              edges={topologyState.topology.edges}
              state={topologyState.runState}
            />
            <PathInspection path={topologyState.activePath} />
            <RelationshipInspector edge={topologyState.selectedEdge} />
          </div>
        </>
      ) : null}
    </div>
  )
}
