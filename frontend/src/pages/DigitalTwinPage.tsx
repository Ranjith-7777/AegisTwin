import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { AttackPathsPanel } from '../components/topology/AttackPathsPanel'
import { BlastRadiusPanel } from '../components/topology/BlastRadiusPanel'
import { PurpleTeamPanel } from '../components/topology/PurpleTeamPanel'
import { CyberDigitalTwin } from '../components/topology/CyberDigitalTwin'
import { TopologyControls } from '../components/topology/TopologyControls'
import { TopologyHistory } from '../components/topology/TopologyHistory'
import {
  AssetInspector,
  PathInspection,
  PathLegend,
  RelationshipInspector,
  ZoneGroup,
} from '../components/topology/TopologyPanels'
import { Button } from '../components/ui/button'
import { useTopology } from '../hooks/useTopology'
import { useSimulationPlayback } from '../hooks/useSimulationPlayback'
import { getDetectionModels } from '../services/detectionApi'
import { getSimulationRuns } from '../services/simulationApi'
import type { DetectionModel } from '../types/detection'
import type { SimulationRun } from '../types/simulation'
import type { TopologyPathType } from '../types/topology'
import { getResponseSummary } from '../services/responseApi'
import type { ResponseImpactSimulation } from '../types/response'
import { listOrchestrations } from '../services/orchestrationApi'
import type { SyntheticExecution } from '../types/orchestration'

type DigitalTwinTab = 'topology' | 'attack-paths' | 'blast-radius' | 'purple-team'
type InspectorTab = 'asset' | 'path' | 'relationship' | 'history'

const TABS: { id: DigitalTwinTab; label: string }[] = [
  { id: 'topology', label: 'Topology' },
  { id: 'attack-paths', label: 'Attack Paths' },
  { id: 'blast-radius', label: 'Blast Radius' },
  { id: 'purple-team', label: 'Purple Team' },
]

const INSPECTOR_TABS: { id: InspectorTab; label: string }[] = [
  { id: 'asset', label: 'Asset' },
  { id: 'path', label: 'Path' },
  { id: 'relationship', label: 'Link' },
  { id: 'history', label: 'History' },
]

export function DigitalTwinPage() {
  const [tab, setTab] = useState<DigitalTwinTab>('topology')
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>('asset')
  const [controlsOpen, setControlsOpen] = useState(false)
  const playback = useSimulationPlayback()
  const topologyState = useTopology(playback.activeRun?.scenario_id === 'staged-compromise-demo')
  const [runs, setRuns] = useState<SimulationRun[]>([])
  const [models, setModels] = useState<DetectionModel[]>([])
  const [source, setSource] = useState('external-user-01')
  const [destination, setDestination] = useState('cloud-database-01')
  const [pathType, setPathType] = useState<TopologyPathType>('expected')
  const [searchParams, setSearchParams] = useSearchParams()
  // Run/model/sequence context is mirrored into the URL (?run=&model=&seq=) so a
  // hard reload or a shared link restores the same view instead of resetting to
  // "no run selected" — see docs/ui/PHASE_2_DESIGN_SYSTEM.md, "Run context".
  const [runId, setRunId] = useState(searchParams.get('run') ?? '')
  const [modelId, setModelId] = useState(searchParams.get('model') ?? '')
  const [sequence, setSequence] = useState(() => {
    const raw = Number(searchParams.get('seq'))
    return Number.isFinite(raw) && raw > 0 ? raw : 1
  })
  const [layers, setLayers] = useState({ observed: true, correlated: true, predicted: true })
  const [followLive, setFollowLive] = useState(true)
  const [reducedMotion, setReducedMotion] = useState(false)
  const [responseImpact, setResponseImpact] = useState<ResponseImpactSimulation | null>(null)
  const [syntheticExecution, setSyntheticExecution] = useState<SyntheticExecution | null>(null)
  // The page tracks two independent notions of "current run": a live playback
  // session (playback.activeRun, driven from the Telemetry page's WebSocket)
  // and the run selected/restored here for topology inspection (runId, which
  // survives a hard reload via the URL). The status line must reflect
  // whichever one is actually driving what the canvas shows: live playback
  // takes precedence when one is active (the canvas overlays liveTopology in
  // that case too), otherwise the restored/selected run context is shown
  // instead of a misleading "Run: none".
  const restoredRun = runId ? (runs.find((item) => item.simulation_run_id === runId) ?? null) : null
  const displayRunId = playback.activeRun?.simulation_run_id ?? (runId || null)
  const displayModelId = playback.activeRun
    ? (playback.selectedModel?.model_id ?? null)
    : modelId || null
  const displaySequence = playback.activeRun ? playback.currentEventIndex : runId ? sequence : 0
  const displayTotal = playback.activeRun
    ? playback.totalEventCount
    : (restoredRun?.event_count ?? 0)
  const displayPlaybackLabel = playback.activeRun
    ? playback.playbackState
    : runId
      ? 'restored'
      : 'idle'

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
        // Restore (or gracefully drop) the run context carried in the URL now
        // that the real run list is known. A stale/unknown run id is cleared
        // rather than left selected against nonexistent data.
        if (runId) {
          const known = runItems.some((item) => item.simulation_run_id === runId)
          if (known) {
            void topologyState.loadRunState(runId, modelId || undefined, sequence)
          } else {
            setRunId('')
            setModelId('')
            setSequence(1)
            setSearchParams((current) => {
              const next = new URLSearchParams(current)
              next.delete('run')
              next.delete('model')
              next.delete('seq')
              return next
            })
          }
        }
      })
      .catch(() => undefined)
    // Runs once on mount to restore URL-carried context; intentionally not
    // re-run when runId/modelId/sequence change afterwards.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function updateParams(next: { run?: string; model?: string; seq?: number }) {
    setSearchParams((current) => {
      const params = new URLSearchParams(current)
      if (next.run !== undefined) {
        if (next.run) params.set('run', next.run)
        else params.delete('run')
      }
      if (next.model !== undefined) {
        if (next.model) params.set('model', next.model)
        else params.delete('model')
      }
      if (next.seq !== undefined) params.set('seq', String(next.seq))
      return params
    })
  }

  function changeRun(value: string) {
    setRunId(value)
    setModelId('')
    setSequence(1)
    setResponseImpact(null)
    setSyntheticExecution(null)
    updateParams({ run: value, model: '', seq: 1 })
    if (value) void topologyState.loadRunState(value, undefined, 1)
  }

  function changeModel(value: string) {
    setModelId(value)
    updateParams({ model: value })
  }

  function changeSequence(value: number) {
    setSequence(value)
    updateParams({ seq: value })
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
    <div className={tab === 'topology' ? 'viewport-page' : 'space-y-6'}>
      <div className="twin-header">
        <div>
          <h1>Cloud Digital Twin</h1>
          <p>Inspect the synthetic cloud estate and sequence-bounded path evidence.</p>
        </div>
        <span className="chip chip-muted">
          {playback.activeRun
            ? 'Live synthetic replay'
            : runId
              ? 'Restored replay'
              : 'Static topology'}
        </span>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Digital Twin views">
          {TABS.map((item) => (
            <Button
              key={item.id}
              role="tab"
              aria-selected={tab === item.id}
              variant={tab === item.id ? 'default' : 'outline'}
              size="sm"
              onClick={() => {
                setTab(item.id)
              }}
            >
              {item.label}
            </Button>
          ))}
        </div>
        <p className="twin-status-line" aria-live="polite">
          <strong>{displayPlaybackLabel}</strong> · run{' '}
          {displayRunId ? displayRunId.slice(0, 8) : 'none'}
          {displayModelId ? ` · model ${displayModelId.slice(0, 8)}` : ''} · seq {displaySequence}/
          {displayTotal}
        </p>
      </div>
      {tab === 'attack-paths' ? (
        <AttackPathsPanel
          nodes={topologyState.topology?.nodes ?? []}
          runId={runId}
          modelId={modelId}
          sequence={sequence}
        />
      ) : null}
      {tab === 'blast-radius' ? (
        <BlastRadiusPanel
          nodes={topologyState.topology?.nodes ?? []}
          runId={runId}
          sequence={sequence}
        />
      ) : null}
      {tab === 'purple-team' ? <PurpleTeamPanel /> : null}
      {tab !== 'topology' ? null : topologyState.error ? (
        <p className="text-red-700" role="alert">
          {topologyState.error}
        </p>
      ) : null}
      {tab === 'topology' && topologyState.loading ? <p>Loading synthetic topology…</p> : null}
      {tab === 'topology' && topologyState.topology ? (
        <div className="twin-workspace-main">
          <div className="twin-canvas-frame">
            <div className="twin-floating-toolbar">
              <span>
                {topologyState.topology.nodes.length} assets · {topologyState.topology.edges.length}{' '}
                links
              </span>
              {(['observed', 'correlated', 'predicted'] as const).map((layer) => (
                <label key={layer}>
                  <input
                    type="checkbox"
                    checked={layers[layer]}
                    onChange={(event) => {
                      setLayers((current) => ({ ...current, [layer]: event.target.checked }))
                    }}
                  />
                  {layer}
                </label>
              ))}
              <label>
                <input
                  type="checkbox"
                  checked={followLive}
                  onChange={(event) => {
                    setFollowLive(event.target.checked)
                  }}
                />
                follow event
              </label>
              <button
                type="button"
                className="twin-controls-toggle"
                onClick={() => {
                  setControlsOpen((value) => !value)
                }}
              >
                {controlsOpen ? 'Close controls' : 'Controls & path query'}
              </button>
            </div>
            {controlsOpen ? (
              <div className="twin-controls-panel">
                <div className="space-y-3">
                  <ZoneGroup />
                  <PathLegend />
                  <div className="flex flex-wrap gap-4 text-sm">
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
                    <button className="text-blue-600" onClick={playback.resetTopologyOverlay}>
                      Reset topology overlay
                    </button>
                    <button
                      className="text-emerald-700"
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
                        className="text-slate-600"
                        onClick={() => {
                          setResponseImpact(null)
                        }}
                      >
                        Clear simulated response impact
                      </button>
                    ) : null}
                    <button
                      className="text-violet-700"
                      disabled={!runId}
                      onClick={() => {
                        void listOrchestrations().then((rows) => {
                          const execution = rows.find((item) => item.simulation_run_id === runId)
                            ?.executions[0]
                          setSyntheticExecution(execution ?? null)
                        })
                      }}
                    >
                      Show applied synthetic execution
                    </button>
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
                    onModel={changeModel}
                    onSequence={changeSequence}
                    onQuery={query}
                  />
                  <p className="text-xs text-amber-700">
                    Observed/anomalous states describe synthetic replay evidence and do not confirm
                    compromise.
                  </p>
                </div>
              </div>
            ) : null}
            <CyberDigitalTwin
              topology={topologyState.topology}
              runState={visibleRunState}
              onSelectNode={topologyState.selectNode}
              onSelectEdge={topologyState.selectEdge}
              liveOverlay={playback.liveTopology}
              animationPaused={playback.playbackState === 'paused' || reducedMotion}
              responseImpact={responseImpact}
              syntheticExecution={syntheticExecution}
              variant="workspace"
            />
            {(syntheticExecution ?? responseImpact) ? (
              <p className="twin-canvas-note" aria-live="polite">
                {syntheticExecution
                  ? `${syntheticExecution.execution_state === 'rolled_back_simulated' ? 'Restored by synthetic rollback' : 'Applied in synthetic twin'}: ${String(syntheticExecution.changed_node_ids.length)} nodes, ${String(syntheticExecution.changed_edge_ids.length)} links.`
                  : null}
                {responseImpact
                  ? `Simulated response impact: hypothetically restricted ${String(responseImpact.changed_node_ids.length)} nodes, ${String(responseImpact.changed_edge_ids.length)} edges.`
                  : null}
              </p>
            ) : null}
          </div>
          <aside className="twin-inspector" aria-label="Selected workload inspector">
            <div className="twin-inspector-tabs" role="tablist" aria-label="Inspector views">
              {INSPECTOR_TABS.map((item) => (
                <button
                  key={item.id}
                  role="tab"
                  aria-selected={inspectorTab === item.id}
                  className={
                    inspectorTab === item.id ? 'twin-inspector-tab is-active' : 'twin-inspector-tab'
                  }
                  onClick={() => {
                    setInspectorTab(item.id)
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <div className="twin-inspector-body">
              {inspectorTab === 'asset' ? (
                <AssetInspector
                  node={topologyState.selectedNode}
                  edges={topologyState.topology.edges}
                  state={topologyState.runState}
                  live={playback.liveTopology}
                  bare
                />
              ) : null}
              {inspectorTab === 'path' ? (
                <PathInspection path={topologyState.activePath} bare />
              ) : null}
              {inspectorTab === 'relationship' ? (
                <RelationshipInspector
                  edge={topologyState.selectedEdge}
                  live={playback.liveTopology}
                  bare
                />
              ) : null}
              {inspectorTab === 'history' ? (
                <TopologyHistory
                  items={playback.liveTopology.history}
                  onSelect={(item) => {
                    const assetId = item.destination_asset_id ?? item.source_asset_id
                    const asset = topologyState.topology?.nodes.find(
                      (node) => node.asset_id === assetId,
                    )
                    if (asset) topologyState.selectNode(asset)
                  }}
                  bare
                />
              ) : null}
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  )
}
