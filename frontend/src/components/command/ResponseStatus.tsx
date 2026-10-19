import { ArrowRight, Check, Play, RotateCcw } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import { useAutonomyWorkflow } from '../../hooks/useAutonomyWorkflow'
import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { autonomyLabel } from '../../lib/autonomy'
import { orchestrationState } from '../../lib/orchestrationState'
import { STATUS_LABEL } from '../../lib/workflowStages'
import { cn } from '../../lib/utils'
import { Button } from '../ui/button'
import { Bar } from '../ui/panel'
import { useDecisionActions } from '../workflow/useDecisionActions'

/**
 * One compact card answering "what are the agents doing right now?": the
 * Red Agent replay, the Blue Agent's selected response with its single next
 * human action, and the eight-step lifecycle. Detail lives on Workflow &
 * Agents.
 */
export function ResponseStatus() {
  const playback = useSimulationPlayback()
  const workflow = useAutonomyWorkflow()
  const actions = useDecisionActions()
  const navigate = useNavigate()
  const run = playback.activeRun
  const comparison = workflow.result?.comparison ?? null
  const selected = actions.selected
  const orchestration = workflow.orchestration
  const state = orchestration ? orchestrationState(orchestration.current_state) : null
  const canRun = workflow.canRun && (workflow.session?.can_operate ?? false)
  const scenario = run
    ? (playback.scenarios.find((item) => item.scenario_id === run.scenario_id)?.name ??
      run.scenario_id)
    : null
  const focus = workflow.rail.find((step) =>
    ['running', 'awaiting', 'blocked', 'failed'].includes(step.status),
  )

  return (
    <section className="panel" aria-label="Response status">
      <header className="panel-head">
        <h2 className="panel-title">Response status</h2>
        {workflow.autonomy ? (
          <span className="text-[0.8rem] text-[var(--text-faint)]">
            {autonomyLabel(workflow.autonomy.mode)} mode
          </span>
        ) : null}
      </header>
      <div className="panel-body status-stack">
        <div className="status-block">
          <p className="status-label">Red Agent</p>
          {run ? (
            <>
              <p className="status-value" title={scenario ?? undefined}>
                {scenario}
              </p>
              <div className="flex items-center gap-3">
                <Bar
                  value={
                    playback.totalEventCount
                      ? playback.currentEventIndex / playback.totalEventCount
                      : 0
                  }
                  tone={playback.playbackState === 'playing' ? 'danger' : 'ok'}
                  label="Replay progress"
                />
                <span className="status-meta whitespace-nowrap">
                  {playback.playbackState === 'completed'
                    ? 'Replay complete'
                    : `${String(playback.currentEventIndex)}/${String(playback.totalEventCount)} events`}
                </span>
              </div>
            </>
          ) : (
            <p className="status-meta">Idle - no scenario is running.</p>
          )}
        </div>

        <div className="status-block" aria-label="Blue Agent decision">
          <p className="status-label">Blue Agent</p>
          {selected ? (
            <>
              <p className="status-value" title={selected.playbook_name}>
                {selected.playbook_name}
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <span className={`state-pill tone-${state?.tone ?? 'accent'}`}>
                  {state?.label ?? 'Recommended'}
                </span>
                {actions.pending ? (
                  <Button
                    size="sm"
                    variant="soft"
                    disabled={!actions.canApprove || actions.busy}
                    title={actions.canApprove ? undefined : 'Requires ADMIN'}
                    onClick={() => {
                      actions.open('approve')
                    }}
                  >
                    <Check /> Approve
                  </Button>
                ) : actions.canExecuteApproved ? (
                  <Button
                    size="sm"
                    variant="soft"
                    disabled={!actions.canOperate || actions.busy}
                    onClick={actions.executeApproved}
                  >
                    <Play /> Execute
                  </Button>
                ) : actions.rollbackAvailable ? (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!actions.canRollback || actions.busy}
                    title={actions.canRollback ? undefined : 'Rollback requires the ADMIN role.'}
                    onClick={() => {
                      actions.open('rollback')
                    }}
                  >
                    <RotateCcw /> Roll back
                  </Button>
                ) : null}
                {workflow.actionPending ? (
                  <span className="status-meta flex items-center gap-1.5">
                    <span className="spinner" aria-hidden="true" /> {workflow.actionPending}…
                  </span>
                ) : null}
              </div>
            </>
          ) : comparison ? (
            <p className="status-meta">
              {comparison.candidates.length} plans simulated; none passed every policy.
            </p>
          ) : workflow.status === 'running' ? (
            <p className="status-meta flex items-center gap-2">
              <span className="spinner" aria-hidden="true" /> Ranking candidate responses…
            </p>
          ) : orchestration ? (
            <span className={`state-pill tone-${state?.tone ?? 'neutral'}`}>{state?.label}</span>
          ) : workflow.canRun ? (
            <div className="grid gap-2">
              <p className="status-meta">An incident is correlated and ready for a response.</p>
              <div>
                <Button
                  size="sm"
                  onClick={() => void workflow.runWorkflow()}
                  disabled={!canRun}
                  title={canRun ? undefined : 'Requires the ANALYST role or higher.'}
                >
                  <Play /> Run Blue workflow
                </Button>
              </div>
            </div>
          ) : (
            <p className="status-meta">Waiting for a correlated incident.</p>
          )}
          {workflow.error ? (
            <p className="m-0 text-[0.8rem] text-[var(--danger-text)]" role="alert">
              {workflow.error}
            </p>
          ) : null}
        </div>

        <div className="status-block">
          <p className="status-label">
            Lifecycle
            <span className="status-meta">
              {' · '}
              {focus
                ? `${focus.label}: ${STATUS_LABEL[focus.status]}`
                : workflow.rail.every((step) => step.status === 'waiting')
                  ? 'not started'
                  : 'complete'}
            </span>
          </p>
          <ol className="dot-rail" aria-label="Autonomous workflow progress">
            {workflow.rail.map((step) => (
              <li key={step.id}>
                <button
                  type="button"
                  className={cn('dot-step', `st-${step.status}`)}
                  aria-label={`${step.label}: ${STATUS_LABEL[step.status]}. ${step.detail}`}
                  data-tip={`${step.label} · ${STATUS_LABEL[step.status]}`}
                  onClick={() => {
                    void navigate(`/workflow?stage=${step.stageIds[0] ?? ''}`)
                  }}
                >
                  <span className="dot-step-mark" aria-hidden="true" />
                  <span className="dot-step-name">{step.label}</span>
                </button>
              </li>
            ))}
          </ol>
          <div className="dot-rail-ends" aria-hidden="true">
            <span>Red Agent</span>
            <span>Recovery</span>
          </div>
        </div>
      </div>
      <footer className="panel-foot flex items-center justify-between gap-3">
        <span>
          {workflow.audit
            ? `audit chain ${workflow.audit.valid ? 'valid' : 'BROKEN'}`
            : 'audit pending'}
        </span>
        <Link className="card-link" to="/workflow">
          Workflow & Agents <ArrowRight className="size-3.5" />
        </Link>
      </footer>
      {actions.element}
    </section>
  )
}
