import {
  ChevronDown,
  Crosshair,
  ListFilter,
  Maximize2,
  Minimize2,
  PanelRight,
  SlidersHorizontal,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { AttackPathsPanel } from '../components/topology/AttackPathsPanel'
import { assetIcon } from '../components/topology/assetIcon'
import { BlastRadiusPanel } from '../components/topology/BlastRadiusPanel'
import { CyberDigitalTwin } from '../components/topology/CyberDigitalTwin'
import { LayersMenu } from '../components/topology/LayersMenu'
import { DEFAULT_VIEW_OPTIONS } from '../components/topology/twinView'
import { PlaybackTimeline } from '../components/topology/PlaybackTimeline'
import { PurpleTeamPanel } from '../components/topology/PurpleTeamPanel'
import { TopologyControls } from '../components/topology/TopologyControls'
import {
  PathInspection,
  PathLegend,
  RelationshipInspector,
} from '../components/topology/TopologyPanels'
import { TwinAssetInspector } from '../components/topology/TwinAssetInspector'
import { TwinLegend, TwinStateBanner } from '../components/topology/TwinLegend'
import { useAutonomyWorkflow } from '../hooks/useAutonomyWorkflow'
import { useSimulationPlayback } from '../hooks/useSimulationPlayback'
import { useTopology } from '../hooks/useTopology'
import { humanize } from '../lib/orchestrationState'
import { getDetectionModels } from '../services/detectionApi'
import { listOrchestrations } from '../services/orchestrationApi'
import { getSimulationRuns } from '../services/simulationApi'
import type { DetectionModel } from '../types/detection'
import type { Orchestration } from '../types/orchestration'
import type { SimulationRun } from '../types/simulation'
import type { TopologyPathType } from '../types/topology'

type DigitalTwinTab = 'topology' | 'attack-paths' | 'blast-radius' | 'purple-team'

const SINK_TYPE = 'synthetic_external_sink'

/** Popover filtering the canvas to one zone (others are dimmed, never hidden). */
function ZoneFilter({
  zones,
  value,
  onChange,
}: {
  zones: string[]
  value: string | null
  onChange: (zone: string | null) => void
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    function onPointer(event: PointerEvent) {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false)
    }
    window.addEventListener('pointerdown', onPointer)
    return () => {
      window.removeEventListener('pointerdown', onPointer)
    }
  }, [open])
  return (
    <div className="relative" ref={root}>
      <button
        type="button"
        className="menu-button"
        aria-expanded={open}
        aria-haspopup="true"
        onClick={() => {
          setOpen((current) => !current)
        }}
      >
        <ListFilter aria-hidden="true" />
        Zone
        {value ? <span className="menu-count">1</span> : null}
        <ChevronDown aria-hidden="true" />
      </button>
      {open ? (
        <div className="popover w-[13rem]" role="group" aria-label="Zone filter">
          <p className="popover-title">Highlight zone</p>
          {[null, ...zones].map((zone) => (
            <label key={zone ?? 'all'} className="popover-check">
              <input
                type="radio"
                name="twin-zone"
                checked={value === zone}
                onChange={() => {
                  onChange(zone)
                  setOpen(false)
                }}
              />
              {zone ? humanize(zone.replace(/_zone$/, '')) : 'All zones'}
            </label>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function DigitalTwinPage({ initialTab = 'topology' }: { initialTab?: DigitalTwinTab }) {
  // The router remounts this page per tab route (see app/router.tsx keys).
  const tab = initialTab
  const [controlsOpen, setControlsOpen] = useState(false)
  const playback = useSimulationPlayback()
  const workflow = useAutonomyWorkflow()
  const topologyState = useTopology(playback.activeRun?.scenario_id === 'staged-compromise-demo')
  const [runs, setRuns] = useState<SimulationRun[]>([])
  const [models, setModels] = useState<DetectionModel[]>([])
  const [source, setSource] = useState('external-user-01')
  const [destination, setDestination] = useState('cloud-database-01')
  const [pathType, setPathType] = useState<TopologyPathType>('expected')
  const [searchParams, setSearchParams] = useSearchParams()
  // Run/model/sequence context is mirrored into the URL (?run=&model=&seq=)
  // so a reload or a shared link restores the same view.
  const [runId, setRunId] = useState(searchParams.get('run') ?? '')
  const [modelId, setModelId] = useState(searchParams.get('model') ?? '')
  const [sequence, setSequence] = useState(() => {
    const raw = Number(searchParams.get('seq'))
    return Number.isFinite(raw) && raw > 0 ? raw : 1
  })
  const [view, setView] = useState(DEFAULT_VIEW_OPTIONS)
  const [zone, setZone] = useState<string | null>(null)
  const [inspecting, setInspecting] = useState<'asset' | 'link'>('asset')
  // The inspector is a drawer: closed until an asset is chosen or it is asked for.
  const [inspectorOpen, setInspectorOpen] = useState(() => searchParams.has('asset'))
  const [legendOpen, setLegendOpen] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const stage = useRef<HTMLElement>(null)
  const [restored, setRestored] = useState<{ runId: string; item: Orchestration | null }>({
    runId: '',
    item: null,
  })

  // Live playback takes precedence; otherwise the restored/selected run is shown.
  const liveRunId = playback.activeRun?.simulation_run_id ?? null
  const restoredRun = runId ? (runs.find((item) => item.simulation_run_id === runId) ?? null) : null
  const displayRunId = liveRunId ?? (runId || null)
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

  // Executed mitigation comes only from a persisted orchestration record.
  const orchestration = liveRunId
    ? workflow.orchestration
    : restored.runId === runId && runId
      ? restored.item
      : null
  const execution = orchestration?.executions[0] ?? null
  const comparison = liveRunId ? (workflow.result?.comparison ?? null) : null
  const selectedCandidate = comparison?.candidates.find((item) => item.recommended) ?? null
  const proposal = useMemo(
    () =>
      view.showProposed && selectedCandidate && !execution
        ? {
            changed_node_ids: selectedCandidate.changed_node_ids,
            changed_edge_ids: selectedCandidate.changed_edge_ids,
          }
        : null,
    [execution, selectedCandidate, view.showProposed],
  )

  useEffect(() => {
    void Promise.all([getSimulationRuns(), getDetectionModels()])
      .then(([runItems, modelItems]) => {
        setRuns(runItems)
        setModels(modelItems.filter((item) => item.synthetic))
        // Restore (or drop) the run context carried in the URL now that the
        // real run list is known. A stale run id is cleared, never kept.
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
    // Runs once on mount to restore URL-carried context.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!runId || liveRunId) return
    let cancelled = false
    void listOrchestrations()
      .then((items) => {
        if (cancelled) return
        const match = items
          .filter((item) => item.simulation_run_id === runId)
          .sort((left, right) => right.updated_at.localeCompare(left.updated_at))[0]
        setRestored({ runId, item: match ?? null })
      })
      .catch(() => {
        if (!cancelled) setRestored({ runId, item: null })
      })
    return () => {
      cancelled = true
    }
  }, [liveRunId, runId])

  // ?asset= (from the header search) selects that asset once the topology loads.
  const topology = topologyState.topology
  const requestedAsset = searchParams.get('asset')
  const { selectNode } = topologyState
  useEffect(() => {
    if (!topology || !requestedAsset) return
    const match = topology.nodes.find((node) => node.asset_id === requestedAsset)
    if (match) selectNode(match)
  }, [requestedAsset, selectNode, topology])

  useEffect(() => {
    function onChange() {
      setFullscreen(document.fullscreenElement !== null)
    }
    document.addEventListener('fullscreenchange', onChange)
    return () => {
      document.removeEventListener('fullscreenchange', onChange)
    }
  }, [])

  function toggleFullscreen() {
    if (document.fullscreenElement) void document.exitFullscreen()
    else void stage.current?.requestFullscreen()
  }

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
    updateParams({ run: value, model: '', seq: 1 })
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

  const assets = topology?.nodes.filter((node) => node.asset_type !== SINK_TYPE) ?? []
  // Opened without a selection, the drawer shows the asset carrying the
  // strongest replay evidence - or the estate's entry point when there is none.
  const liveNodes = playback.liveTopology.nodes
  const evidencePick =
    assets.find((node) => liveNodes[node.asset_id]?.current_focus) ??
    assets.find((node) => liveNodes[node.asset_id]?.correlated) ??
    assets.find((node) => liveNodes[node.asset_id]?.anomalous_observed) ??
    assets.find((node) => node.asset_type === 'external_client') ??
    assets[0] ??
    null
  const inspectedNode = topologyState.selectedNode ?? evidencePick
  const zones = [...new Set(assets.map((node) => node.zone))]
  const relationships =
    topology?.edges.filter(
      (edge) =>
        assets.some((node) => node.asset_id === edge.source_asset_id) &&
        assets.some((node) => node.asset_id === edge.destination_asset_id),
    ).length ?? 0
  const evidenced = assets.filter((node) => playback.liveTopology.nodes[node.asset_id]?.observed)
  const evidence = selectedCandidate?.security_gain_evidence ?? null
  const passing = comparison?.candidates.filter((item) => item.policy_pass).length ?? 0
  const statusLine = (
    <p className="twin-status-line" aria-live="polite">
      <strong>{displayPlaybackLabel}</strong> · run{' '}
      {displayRunId ? displayRunId.slice(0, 8) : 'none'}
      {displayModelId ? ` · model ${displayModelId.slice(0, 8)}` : ''} · seq {displaySequence}/
      {displayTotal}
    </p>
  )

  if (tab !== 'topology')
    return (
      <div className="page-stack">
        <div className="page-heading">
          <div>
            <h1>Cloud Digital Twin</h1>
            <p>
              Synthetic cloud estate with sequence-bounded path evidence; proposed and executed
              mitigations are kept visibly distinct.
            </p>
          </div>
          {statusLine}
        </div>
        {tab === 'attack-paths' ? (
          <AttackPathsPanel
            nodes={topology?.nodes ?? []}
            runId={runId}
            modelId={modelId}
            sequence={sequence}
          />
        ) : null}
        {tab === 'blast-radius' ? (
          <BlastRadiusPanel nodes={topology?.nodes ?? []} runId={runId} sequence={sequence} />
        ) : null}
        {tab === 'purple-team' ? <PurpleTeamPanel /> : null}
      </div>
    )

  const summary = [
    `${String(assets.length)} assets`,
    `${String(relationships)} relationships`,
    playback.activeRun && assets.length
      ? `evidence on ${String(Math.round((evidenced.length / assets.length) * 100))}% of assets`
      : null,
    evidence
      ? `attack paths ${String(evidence.attack_paths_before)} → ${String(evidence.attack_paths_after)} with the selected plan`
      : null,
    comparison
      ? `${String(comparison.candidates.length)} options · ${String(passing)} pass policy`
      : null,
  ].filter(Boolean)

  return (
    <div className="page-stack">
      {topologyState.error ? (
        <p className="error-state" role="alert">
          {topologyState.error}
        </p>
      ) : null}

      <div className={inspectorOpen ? 'twin-main has-drawer' : 'twin-main'}>
        <section className="panel twin-stage" ref={stage} aria-label="Digital twin canvas">
          <header className="twin-stage-head">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1>Cloud Digital Twin</h1>
                <span className="chip chip-muted">
                  {playback.activeRun
                    ? 'Live synthetic replay'
                    : runId
                      ? 'Restored replay'
                      : 'Static topology'}
                </span>
              </div>
              <p>
                Synthetic estate with sequence-bounded path evidence; proposed and executed
                mitigations are kept distinct.
              </p>
              <p className="twin-summary">{summary.join(' · ')}</p>
            </div>
            <div className="twin-toolbar">
              <LayersMenu value={view} onChange={setView} />
              <ZoneFilter zones={zones} value={zone} onChange={setZone} />
              <button
                type="button"
                className="menu-button"
                aria-expanded={controlsOpen}
                onClick={() => {
                  setControlsOpen((value) => !value)
                }}
              >
                <SlidersHorizontal aria-hidden="true" />
                Run context
              </button>
              <button
                type="button"
                className="menu-button"
                aria-expanded={inspectorOpen}
                aria-controls="twin-inspector"
                onClick={() => {
                  setInspectorOpen((value) => !value)
                }}
              >
                <PanelRight aria-hidden="true" />
                Inspector
              </button>
              <button
                type="button"
                className="icon-btn"
                onClick={toggleFullscreen}
                aria-label={fullscreen ? 'Exit full screen' : 'Full screen'}
              >
                {fullscreen ? <Minimize2 aria-hidden="true" /> : <Maximize2 aria-hidden="true" />}
              </button>
            </div>
          </header>
          <div className="twin-canvas-area">
            {topologyState.loading ? (
              <p className="empty-state h-full">
                <span className="spinner" aria-hidden="true" /> Loading synthetic topology…
              </p>
            ) : null}
            {topology ? (
              <CyberDigitalTwin
                topology={topology}
                runState={topologyState.runState}
                layers={view.layers}
                onSelectNode={(node) => {
                  topologyState.selectNode(node)
                  setInspecting('asset')
                  setInspectorOpen(true)
                }}
                onSelectEdge={(edge) => {
                  topologyState.selectEdge(edge)
                  setInspecting('link')
                  setInspectorOpen(true)
                }}
                selectedNodeId={
                  inspectorOpen && inspecting === 'asset' ? (inspectedNode?.asset_id ?? null) : null
                }
                liveOverlay={playback.liveTopology}
                animationPaused={playback.playbackState === 'paused' || view.reducedMotion}
                responseImpact={proposal}
                syntheticExecution={execution}
                variant="workspace"
                focusActive={
                  playback.playbackState === 'playing' || playback.playbackState === 'paused'
                }
                showMiniMap={false}
                zoneFilter={zone}
              />
            ) : null}
            <div className="twin-legend-dock">
              <button
                type="button"
                className="menu-button"
                aria-expanded={legendOpen}
                aria-controls="twin-legend"
                onClick={() => {
                  setLegendOpen((value) => !value)
                }}
              >
                {legendOpen ? 'Hide legend' : 'Legend'}
              </button>
              {legendOpen ? <TwinLegend /> : null}
            </div>
            <TwinStateBanner
              execution={execution}
              proposedCount={
                proposal ? proposal.changed_node_ids.length + proposal.changed_edge_ids.length : 0
              }
              attackActive={playback.playbackState === 'playing'}
            />
            {controlsOpen && topology ? (
              <div className="twin-controls-panel">
                <div className="grid gap-3">
                  <div className="flex items-center justify-between">
                    <h2 className="panel-title">
                      <Crosshair className="size-4" /> Run context & path query
                    </h2>
                    <button
                      className="card-link"
                      onClick={() => {
                        setControlsOpen(false)
                      }}
                    >
                      Close
                    </button>
                  </div>
                  <PathLegend />
                  <TopologyControls
                    nodes={topology.nodes}
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
                    onModel={(value) => {
                      setModelId(value)
                      updateParams({ model: value })
                    }}
                    onSequence={(value) => {
                      setSequence(value)
                      updateParams({ seq: value })
                    }}
                    onQuery={query}
                  />
                  {topologyState.activePath ? (
                    <PathInspection path={topologyState.activePath} bare />
                  ) : null}
                  <div className="btn-row">
                    <button className="card-link" onClick={playback.resetTopologyOverlay}>
                      Reset live overlay
                    </button>
                  </div>
                  <p className="m-0 text-[0.8rem] text-[var(--warn-text)]">
                    Observed and anomalous states describe synthetic replay evidence; they never
                    confirm a real compromise.
                  </p>
                </div>
              </div>
            ) : null}
          </div>
          <PlaybackTimeline statusLine={statusLine} />
        </section>
        {!inspectorOpen ? null : inspecting === 'link' && topologyState.selectedEdge ? (
          <section className="panel asset-inspector" id="twin-inspector" aria-label="Selected link">
            <header className="panel-head is-ruled">
              <h2 className="panel-title">Relationship</h2>
              <button
                type="button"
                className="card-link"
                onClick={() => {
                  setInspecting('asset')
                }}
              >
                Back to asset
              </button>
            </header>
            <div className="panel-body is-scroll">
              <RelationshipInspector
                edge={topologyState.selectedEdge}
                live={playback.liveTopology}
                bare
              />
            </div>
          </section>
        ) : (
          <TwinAssetInspector
            node={inspectedNode}
            edges={topology?.edges ?? []}
            icon={inspectedNode ? assetIcon(inspectedNode.asset_type) : null}
            onClose={() => {
              topologyState.selectNode(null)
              setInspectorOpen(false)
            }}
          />
        )}
      </div>
    </div>
  )
}
