import { useEffect, useMemo, useState } from 'react'

import { CyberDigitalTwin } from '../components/topology/CyberDigitalTwin'
import { TopologyControls } from '../components/topology/TopologyControls'
import { TopologyHistory } from '../components/topology/TopologyHistory'
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
import { useSimulationPlayback } from '../hooks/useSimulationPlayback'
import { getDetectionModels } from '../services/detectionApi'
import { getSimulationRuns } from '../services/simulationApi'
import type { DetectionModel } from '../types/detection'
import type { SimulationRun } from '../types/simulation'
import type { TopologyPathType } from '../types/topology'
import { getResponseSummary } from '../services/responseApi'
import type { ResponseImpactSimulation } from '../types/response'

export function DigitalTwinPage() {
  const playback = useSimulationPlayback()
  const topologyState = useTopology(playback.activeRun?.scenario_id === 'staged-compromise-demo')
  const [runs, setRuns] = useState<SimulationRun[]>([])
  const [models, setModels] = useState<DetectionModel[]>([])
  const [source, setSource] = useState('employee-laptop-01')
  const [destination, setDestination] = useState('examination-database-01')
  const [pathType, setPathType] = useState<TopologyPathType>('expected')
  const [runId, setRunId] = useState('')
  const [modelId, setModelId] = useState('')
  const [sequence, setSequence] = useState(1)
  const [layers, setLayers] = useState({ observed: true, correlated: true, predicted: true })
  const [followLive, setFollowLive] = useState(true)
  const [reducedMotion, setReducedMotion] = useState(false)
  const [responseImpact, setResponseImpact] = useState<ResponseImpactSimulation | null>(null)
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
    setResponseImpact(null)
    if (value) void topologyState.loadRunState(value, undefined, 1)
  }

  function query() {
    setResponseImpact(null)
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
        <span className="status-chip">
          {playback.activeRun ? 'LIVE SYNTHETIC REPLAY' : 'STATIC TOPOLOGY'}
        </span>
      </header>
      <p className="text-sm" aria-live="polite">
        Playback: {playback.playbackState} · Run:{' '}
        {playback.activeRun?.simulation_run_id.slice(0, 8) ?? 'none'} · Sequence{' '}
        {playback.currentEventIndex} / {playback.totalEventCount}
      </p>
      <p className="text-xs text-amber-200">
        Observed and anomalous states describe synthetic replay evidence and do not confirm
        compromise.
      </p>
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
              <div className="flex flex-wrap gap-4">
                <label>
                  <input
                    type="checkbox"
                    checked={followLive}
                    onChange={(event) => {
                      setFollowLive(event.target.checked)
                    }}
                  />{' '}
                  Follow current event
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={reducedMotion}
                    onChange={(event) => {
                      setReducedMotion(event.target.checked)
                    }}
                  />{' '}
                  Reduced animation
                </label>
                <button className="text-cyan-300" onClick={playback.resetTopologyOverlay}>
                  Reset topology overlay
                </button>
                <button
                  className="text-emerald-300"
                  disabled={!runId || !modelId}
                  onClick={() => {
                    void getResponseSummary(runId, modelId)
                      .then((summary) => {
                        setResponseImpact(
                          summary.through_sequence_number === sequence
                            ? (summary.top_recommendation?.simulation ?? null)
                            : null,
                        )
                      })
                      .catch(() => {
                        setResponseImpact(null)
                      })
                  }}
                >
                  Show simulated response impact
                </button>
                {responseImpact ? (
                  <button
                    className="text-slate-300"
                    onClick={() => {
                      setResponseImpact(null)
                    }}
                  >
                    Clear simulated response impact
                  </button>
                ) : null}
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
            liveOverlay={playback.liveTopology}
            animationPaused={playback.playbackState === 'paused' || reducedMotion}
            responseImpact={responseImpact}
          />
          {responseImpact ? (
            <p className="text-sm text-emerald-200" aria-live="polite">
              Simulated response impact overlay: hypothetically restricted{' '}
              {responseImpact.changed_node_ids.length} nodes and{' '}
              {responseImpact.changed_edge_ids.length} edges. This does not alter playback and is
              not an actual response.
            </p>
          ) : null}
          <div className="grid gap-6 lg:grid-cols-2">
            <AssetInspector
              node={topologyState.selectedNode}
              edges={topologyState.topology.edges}
              state={topologyState.runState}
              live={playback.liveTopology}
            />
            <PathInspection path={topologyState.activePath} />
            <RelationshipInspector edge={topologyState.selectedEdge} live={playback.liveTopology} />
            <TopologyHistory
              items={playback.liveTopology.history}
              onSelect={(item) => {
                const assetId = item.destination_asset_id ?? item.source_asset_id
                const asset = topologyState.topology?.nodes.find(
                  (node) => node.asset_id === assetId,
                )
                if (asset) topologyState.selectNode(asset)
              }}
            />
          </div>
        </>
      ) : null}
    </div>
  )
}
