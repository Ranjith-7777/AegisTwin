import { ArrowRight, Check, ChevronDown, Play, RefreshCw, RotateCcw, Swords } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { BlueRecommendations } from '../components/agents/BlueRecommendations'
import { IncidentChain } from '../components/agents/IncidentChain'
import { IncidentStepper } from '../components/agents/IncidentStepper'
import {
  EvidenceArtifacts,
  ExecutionState,
  RollbackStatus,
} from '../components/agents/ResponseRecords'
import { StageEvidence } from '../components/agents/StageEvidence'
import { MitreMapping, ScenarioTimeline } from '../components/agents/ThreatIntel'
import { Button } from '../components/ui/button'
import { AutonomyModeSwitch } from '../components/workflow/AutonomyModeSwitch'
import { StageList } from '../components/workflow/StageList'
import { useDecisionActions } from '../components/workflow/useDecisionActions'
import { useAutonomyWorkflow } from '../hooks/useAutonomyWorkflow'
import { parseUtc, useRangeActivity } from '../hooks/useRangeActivity'
import { useSimulationPlayback } from '../hooks/useSimulationPlayback'
import { useTopology } from '../hooks/useTopology'
import { AUTONOMY_MODES } from '../lib/autonomy'
import { currentStage, STATUS_LABEL, type StageId } from '../lib/workflowStages'

const STAGE_IDS: StageId[] = [
  'attack',
  'telemetry',
  'detection',
  'correlation',
  'prediction',
  'response',
  'what_if',
  'policy',
  'approval',
  'execution',
  'verification',
  'rollback',
  'twin',
  'audit',
]

type Tab = 'overview' | 'red' | 'blue' | 'approvals' | 'evidence' | 'stages'

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'red', label: 'Red Agent' },
  { id: 'blue', label: 'Blue Agent' },
  { id: 'approvals', label: 'Approvals & rollback' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'stages', label: 'All stages' },
]

function isStageId(value: string | null): value is StageId {
  return value !== null && (STAGE_IDS as string[]).includes(value)
}

function isTab(value: string | null): value is Tab {
  return TABS.some((item) => item.id === value)
}

function formatSeconds(seconds: number): string {
  if (seconds < 1) return `${String(Math.round(seconds * 1000))} ms`
  if (seconds < 120) return `${seconds.toFixed(1)} s`
  return `${(seconds / 60).toFixed(1)} min`
}

/** The single most useful next action for the current lifecycle state. */
function NextStep({ onTab }: { onTab: (tab: Tab) => void }) {
  const playback = useSimulationPlayback()
  const workflow = useAutonomyWorkflow()
  const actions = useDecisionActions()
  const canRun = workflow.canRun && (workflow.session?.can_operate ?? false)
  let title: string
  let body: string
  let action: ReactNode = null
  if (!playback.activeRun) {
    title = 'Launch a scenario'
    body = 'Nothing is running. Start a scripted Red Agent scenario to exercise the defence loop.'
    action = (
      <Button asChild>
        <Link to="/red-agent">
          <Swords /> Open Red Agent lab
        </Link>
      </Button>
    )
  } else if (!playback.currentIncidentCandidate) {
    title = 'Waiting for correlated evidence'
    body = 'The replay is streaming. The Blue Agent acts once anomalies correlate into an incident.'
  } else if (actions.pending) {
    title = 'Approval required'
    body = `${actions.selected?.playbook_name ?? 'The selected plan'} passed policy and needs a human decision before synthetic execution.`
    action = (
      <Button
        disabled={!actions.canApprove || actions.busy}
        title={actions.canApprove ? undefined : 'Requires ADMIN'}
        onClick={() => {
          actions.open('approve')
        }}
      >
        <Check /> Review & approve
      </Button>
    )
  } else if (actions.canExecuteApproved) {
    title = 'Ready to execute'
    body = 'The plan is approved. Execute it against the twin; it is then verified automatically.'
    action = (
      <Button disabled={!actions.canOperate || actions.busy} onClick={actions.executeApproved}>
        <Play /> Execute & verify
      </Button>
    )
  } else if (workflow.orchestration?.rollback) {
    title = 'Restored'
    body = 'The mitigation was rolled back and the prior twin state restored.'
    action = (
      <Button
        variant="outline"
        onClick={() => {
          onTab('evidence')
        }}
      >
        Review evidence <ArrowRight />
      </Button>
    )
  } else if (actions.rollbackAvailable) {
    title = 'Contained and verified'
    body = 'Verification met the expected objective. Review the decision, or roll the twin back.'
    action = (
      <div className="btn-row">
        <Button
          variant="outline"
          onClick={() => {
            onTab('blue')
          }}
        >
          Why this action <ArrowRight />
        </Button>
        <Button
          variant="outline"
          disabled={!actions.canRollback || actions.busy}
          title={actions.canRollback ? undefined : 'Rollback requires the ADMIN role.'}
          onClick={() => {
            actions.open('rollback')
          }}
        >
          <RotateCcw /> Roll back
        </Button>
      </div>
    )
  } else if (workflow.canRun && !workflow.result && !workflow.orchestration) {
    title = 'Run the Blue workflow'
    body = 'An incident is correlated. Rank candidate responses and apply the autonomy policy.'
    action = (
      <Button
        disabled={!canRun || workflow.status === 'running'}
        onClick={() => void workflow.runWorkflow()}
      >
        <Play /> Run Blue workflow
      </Button>
    )
  } else {
    title = workflow.status === 'running' ? 'Ranking responses…' : 'Response in progress'
    body =
      'The Blue Agent is working through the lifecycle; each step appears above as it completes.'
  }
  return (
    <section className="panel next-step" aria-label="Next step">
      <div className="panel-body">
        <p className="status-label">Next step</p>
        <h2 className="next-step-title">{title}</h2>
        <p className="next-step-body">{body}</p>
        {action ? <div className="mt-4">{action}</div> : null}
      </div>
      {actions.element}
    </section>
  )
}

/**
 * Workflow & Agents: the active incident, its lifecycle, and - one group at a
 * time - the Red Agent evidence, the Blue Agent's ranked responses, the human
 * gates and rollback, and exportable evidence. Every element is backed by a
 * persisted record; the agents are deterministic and policy-governed.
 */
export function WorkflowPage() {
  const workflow = useAutonomyWorkflow()
  const playback = useSimulationPlayback()
  const { topology } = useTopology(playback.activeRun?.scenario_id === 'staged-compromise-demo')
  const [params, setParams] = useSearchParams()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const requested = params.get('stage')
  const focus = currentStage(workflow.stages)
  const selectedId: StageId = isStageId(requested) ? requested : (focus?.id ?? 'attack')
  const orchestration = workflow.orchestration
  const incident = playback.currentIncidentCandidate
  const mode = AUTONOMY_MODES.find((item) => item.mode === workflow.autonomy?.mode)
  const pendingApproval = workflow.stages.some((stage) => stage.status === 'awaiting')
  const requestedTab = params.get('tab')
  const tab: Tab = isTab(requestedTab)
    ? requestedTab
    : isStageId(requested)
      ? 'stages'
      : pendingApproval
        ? 'approvals'
        : 'overview'
  const activity = useRangeActivity(
    playback.runs,
    `${orchestration?.orchestration_id ?? ''}:${orchestration?.updated_at ?? ''}`,
  )
  const decisions = activity.orchestrations.flatMap((item) => item.decisions).length
  const executed = activity.orchestrations.filter((item) => item.executions.length > 0)
  const humanApproved = executed.filter((item) =>
    item.approvals.some((approval) => approval.decided_by !== null),
  ).length
  const verifyTimes = activity.orchestrations
    .map((item) => {
      const check = item.verifications.find(
        (verification) => verification.verification_status === 'successful_simulation',
      )
      return check
        ? (parseUtc(check.completed_at).getTime() - parseUtc(item.created_at).getTime()) / 1000
        : null
    })
    .filter((value): value is number => value !== null && value >= 0)
  const meanVerify = verifyTimes.length
    ? verifyTimes.reduce((sum, value) => sum + value, 0) / verifyTimes.length
    : null
  const stepIndex = focus ? workflow.rail.findIndex((step) => step.stageIds.includes(focus.id)) : -1

  function openTab(next: Tab) {
    setParams(next === 'overview' ? {} : { tab: next }, { replace: true })
  }

  function selectStage(id: StageId) {
    setParams({ tab: 'stages', stage: id }, { replace: true })
  }

  return (
    <div className="page-stack">
      <div className="cc-head">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1>Workflow & Agents</h1>
            {incident ? (
              <span className={`sev sev-${incident.priority}`}>{incident.priority} incident</span>
            ) : null}
          </div>
          <p>
            {incident
              ? `${incident.title} · ${String(incident.involved_asset_ids.length)} assets · ${String(incident.observed_technique_ids.length)} techniques · incident ${incident.incident_candidate_id.slice(0, 8)}`
              : playback.activeRun
                ? 'The replay is running; no incident has been correlated yet.'
                : 'No active incident. Launch a scenario from the Red Agent lab to begin.'}
          </p>
        </div>
        <div className="btn-row">
          <Button
            variant="outline"
            size="icon"
            onClick={() => void workflow.refresh()}
            aria-label="Refresh workflow state"
          >
            <RefreshCw />
          </Button>
          <Button
            variant={workflow.result ? 'outline' : 'default'}
            onClick={() => void workflow.runWorkflow()}
            disabled={
              !workflow.canRun ||
              workflow.status === 'running' ||
              !(workflow.session?.can_operate ?? false)
            }
          >
            <Play /> {workflow.result ? 'Re-run Blue workflow' : 'Run Blue workflow'}
          </Button>
        </div>
      </div>

      <section className="panel" aria-label="Incident workflow">
        <header className="panel-head">
          <div className="min-w-0">
            <h2 className="panel-title">Incident lifecycle</h2>
            <p className="panel-subtitle">
              {focus
                ? `Step ${String(stepIndex + 1)} of ${String(workflow.rail.length)} · ${focus.name}: ${STATUS_LABEL[focus.status]}`
                : 'All steps complete'}
            </p>
          </div>
          <button
            type="button"
            className="menu-button"
            aria-expanded={settingsOpen}
            aria-controls="autonomy-settings"
            onClick={() => {
              setSettingsOpen((value) => !value)
            }}
          >
            {mode ? `${mode.label} mode` : 'Autonomy mode'}
            <ChevronDown aria-hidden="true" />
          </button>
        </header>
        {settingsOpen ? (
          <div className="autonomy-settings" id="autonomy-settings">
            <AutonomyModeSwitch compact />
            <p className="m-0 text-[0.85rem] text-[var(--text-dim)]">
              {mode?.description ?? 'Autonomy mode unavailable.'}
            </p>
            <label className="field-inline text-[0.85rem] text-[var(--text-dim)]">
              <input
                type="checkbox"
                checked={workflow.autoRun}
                onChange={(event) => {
                  workflow.setAutoRun(event.target.checked)
                }}
              />
              Run the Blue workflow automatically when the replay completes
            </label>
          </div>
        ) : null}
        <div className="panel-body">
          <IncidentStepper
            steps={workflow.rail}
            selected={tab === 'stages' ? selectedId : null}
            onSelect={selectStage}
          />
        </div>
      </section>

      <div className="line-tabs is-page" role="tablist" aria-label="Workflow sections">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className="line-tab"
            onClick={() => {
              if (item.id === 'stages') selectStage(selectedId)
              else openTab(item.id)
            }}
          >
            {item.id === 'stages' ? `All ${String(workflow.stages.length)} stages` : item.label}
            {item.id === 'approvals' && pendingApproval ? (
              <span className="nav-badge" aria-label="Approval pending">
                1
              </span>
            ) : null}
          </button>
        ))}
      </div>

      <div role="tabpanel" aria-label={TABS.find((item) => item.id === tab)?.label}>
        {tab === 'overview' ? (
          <div className="wf-grid is-overview">
            <NextStep onTab={openTab} />
            <IncidentChain nodes={topology?.nodes ?? []} />
          </div>
        ) : null}
        {tab === 'red' ? (
          <div className="wf-grid is-halves">
            <ScenarioTimeline />
            <MitreMapping />
          </div>
        ) : null}
        {tab === 'blue' ? (
          <div className="grid gap-4">
            <p className="agent-stats">
              <span>
                <b>{activity.loading ? '—' : decisions}</b> agent decisions across{' '}
                {activity.orchestrations.length} orchestrations
              </span>
              <span>
                <b>{activity.loading ? '—' : executed.length - humanApproved}</b> automatic ·{' '}
                <b>{activity.loading ? '—' : humanApproved}</b> human-approved executions
              </span>
              <span title="Orchestration created → verification completed, wall clock">
                <b>{meanVerify === null ? '—' : formatSeconds(meanVerify)}</b> mean time to verify
              </span>
            </p>
            <BlueRecommendations />
          </div>
        ) : null}
        {tab === 'approvals' ? (
          <div className="wf-grid is-halves">
            <ExecutionState />
            <RollbackStatus />
          </div>
        ) : null}
        {tab === 'evidence' ? <EvidenceArtifacts /> : null}
        {tab === 'stages' ? (
          <section className="panel" aria-label="Lifecycle stages">
            <div className="panel-body pt-4">
              <div className="stage-split">
                <StageList stages={workflow.stages} selected={selectedId} onSelect={selectStage} />
                <div className="inset">
                  <StageEvidence id={selectedId} />
                </div>
              </div>
            </div>
          </section>
        ) : null}
      </div>
    </div>
  )
}
