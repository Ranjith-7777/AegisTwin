import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { AutonomyWorkflowContext } from './autonomyWorkflowContext'
import { useSimulationPlayback } from '../hooks/useSimulationPlayback'
import { meaningfulPrediction } from '../lib/prediction'
import { deriveRail, deriveWorkflowStages, type WorkflowStatus } from '../lib/workflowStages'
import { toClientApiError } from '../services/apiClient'
import { getAutonomyConfig, setAutonomyMode as putAutonomyMode } from '../services/autonomyApi'
import {
  decideApproval,
  executeSynthetic,
  rollbackSynthetic,
  verifyAudit,
  verifySynthetic,
} from '../services/orchestrationApi'
import { getSession } from '../services/sessionApi'
import { getWorkflowState, runWorkflowCoordinator } from '../services/workflowApi'
import type { AutonomyConfig, AutonomyMode } from '../types/autonomy'
import type { AuditIntegrity, Orchestration } from '../types/orchestration'
import type { SessionView } from '../types/session'
import type { WorkflowRunResult } from '../types/workflow'

const OPERATOR = 'Demo Operator (synthetic)'
const AWAITING_POLL_MS = 5_000

interface BlueState {
  key: string | null
  status: WorkflowStatus
  error: string | null
  result: WorkflowRunResult | null
  orchestration: Orchestration | null
  audit: AuditIntegrity | null
}

const EMPTY: Omit<BlueState, 'key'> = {
  status: 'idle',
  error: null,
  result: null,
  orchestration: null,
  audit: null,
}

/**
 * Owns the Blue-side lifecycle for the active Red Agent run: autonomy mode,
 * the Workflow Coordinator result, the live orchestration record, and the
 * audit-chain check. Every stage it exposes is derived from backend records
 * (see lib/workflowStages.ts) - nothing is simulated in the browser.
 */
export function AutonomyWorkflowProvider({ children }: { children: ReactNode }) {
  const playback = useSimulationPlayback()
  const [session, setSession] = useState<SessionView | null>(null)
  const [autonomy, setAutonomy] = useState<AutonomyConfig | null>(null)
  const [autonomyUpdating, setAutonomyUpdating] = useState(false)
  const [autonomyError, setAutonomyError] = useState<string | null>(null)
  const [autoRun, setAutoRun] = useState(true)
  const [actionPending, setActionPending] = useState<string | null>(null)
  // Blue-side state is keyed by run+model, so a previous run's result can
  // never be displayed against a new run.
  const [blue, setBlue] = useState<BlueState>({ key: null, ...EMPTY })
  const autoRanFor = useRef<string | null>(null)

  const runId = playback.activeRun?.simulation_run_id ?? null
  const modelId = playback.selectedModel?.model_id ?? null
  const incident = playback.currentIncidentCandidate
  const runKey = runId ? `${runId}:${modelId ?? ''}` : null
  const current: BlueState = blue.key === runKey ? blue : { key: runKey, ...EMPTY }
  const { status } = current
  // Runs are deterministic, so replaying the same scenario/seed reuses a run
  // that may already carry a persisted workflow (ranked comparison plus
  // orchestration, restored together by the backend). It is only revealed
  // once this replay has reached the evidence the plan was made from - a
  // response is never shown ahead of the attack it answers.
  const replaying = playback.playbackState === 'playing' || playback.playbackState === 'paused'
  const horizon =
    current.result?.comparison?.through_sequence_number ??
    current.orchestration?.through_sequence_number ??
    null
  const revealed = horizon === null || !replaying || playback.currentEventIndex >= horizon
  const result = revealed ? current.result : null
  const orchestration = revealed ? current.orchestration : null
  const audit = revealed ? current.audit : null
  const error = current.error ?? autonomyError

  const patch = useCallback((key: string | null, update: Partial<BlueState>) => {
    setBlue((previous) => ({
      ...(previous.key === key ? previous : { key, ...EMPTY }),
      ...update,
      key,
    }))
  }, [])

  useEffect(() => {
    void getSession()
      .then(setSession)
      .catch(() => {
        setSession(null)
      })
    void getAutonomyConfig()
      .then(setAutonomy)
      .catch(() => {
        setAutonomy(null)
      })
  }, [])

  const adopt = useCallback(
    async (key: string | null, item: Orchestration | null) => {
      patch(key, { orchestration: item, audit: null })
      if (!item) return
      try {
        patch(key, { audit: await verifyAudit(item.orchestration_id) })
      } catch {
        patch(key, { audit: null })
      }
    },
    [patch],
  )

  const refresh = useCallback(async () => {
    if (!runId || !modelId) return
    try {
      const state = await getWorkflowState(runId, modelId)
      if (state) patch(runKey, { result: state })
      await adopt(runKey, state?.orchestration ?? null)
    } catch {
      // Keep the last known state; the next action or poll retries.
    }
  }, [adopt, modelId, patch, runId, runKey])

  // Restore the workflow already persisted for the active run (comparison and
  // orchestration together), e.g. after a reload or a replay of the same
  // deterministic run. State for other runs is ignored (see `current`).
  useEffect(() => {
    if (!runId || !modelId) return
    let cancelled = false
    void getWorkflowState(runId, modelId)
      .then((state) => {
        if (cancelled || !state) return
        patch(runKey, { result: state, status: 'done' })
        void adopt(runKey, state.orchestration)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [adopt, modelId, patch, runId, runKey])

  const canRun = Boolean(runId && modelId && incident)

  const runWorkflow = useCallback(async () => {
    if (!runId || !modelId || !incident) return
    const key = runKey
    const sequence = Math.max(playback.currentEventIndex, incident.latest_sequence_number, 1)
    patch(key, { status: 'running', error: null })
    try {
      const outcome = await runWorkflowCoordinator({
        runId,
        modelId,
        incidentCandidateId: incident.incident_candidate_id,
        throughSequence: sequence,
      })
      patch(key, { result: outcome })
      await adopt(key, outcome.orchestration)
      patch(key, { status: 'done' })
    } catch (reason) {
      patch(key, { status: 'error', error: toClientApiError(reason).message })
    }
  }, [adopt, incident, modelId, patch, playback.currentEventIndex, runId, runKey])

  // Autonomous trigger: once the attack replay has completed and an incident
  // has been correlated, hand the evidence to the Blue workflow exactly once.
  useEffect(() => {
    if (!autoRun || !runKey || !canRun) return
    if (playback.playbackState !== 'completed') return
    if (autoRanFor.current === runKey || status === 'running' || orchestration || result) return
    autoRanFor.current = runKey
    void runWorkflow()
  }, [autoRun, canRun, orchestration, playback.playbackState, result, runKey, runWorkflow, status])

  // While a human gate is open, keep the record fresh in case it is decided
  // from another page or tab.
  const awaiting = orchestration?.current_state.startsWith('awaiting_') ?? false
  useEffect(() => {
    if (!awaiting) return
    const timer = window.setInterval(() => {
      void refresh()
    }, AWAITING_POLL_MS)
    return () => {
      window.clearInterval(timer)
    }
  }, [awaiting, refresh])

  const guarded = useCallback(
    async (label: string, action: () => Promise<Orchestration>) => {
      const key = runKey
      setActionPending(label)
      patch(key, { error: null })
      try {
        const updated = await action()
        await adopt(key, updated)
        return updated
      } catch (reason) {
        patch(key, { error: toClientApiError(reason).message })
        return null
      } finally {
        setActionPending(null)
      }
    },
    [adopt, patch, runKey],
  )

  const executeAndVerify = useCallback(
    async (item: Orchestration) => {
      const executed = await guarded('Executing', () => executeSynthetic(item.orchestration_id))
      if (executed?.current_state === 'synthetic_execution_completed') {
        await guarded('Verifying', () => verifySynthetic(executed.orchestration_id))
      }
    },
    [guarded],
  )

  const approve = useCallback(
    async (reason: string) => {
      const pending = orchestration?.approvals.find((item) => item.approval_state === 'pending')
      if (!orchestration || !pending) return
      const decided = await guarded('Approving', () =>
        decideApproval(orchestration.orchestration_id, pending.approval_request_id, {
          actor_role: pending.required_role,
          actor_display_name: OPERATOR,
          decision: 'approve',
          reason,
        }),
      )
      // The human approval was the remaining gate, so the loop continues.
      if (decided?.current_state === 'approved') await executeAndVerify(decided)
    },
    [executeAndVerify, guarded, orchestration],
  )

  const reject = useCallback(
    async (reason: string) => {
      const pending = orchestration?.approvals.find((item) => item.approval_state === 'pending')
      if (!orchestration || !pending) return
      await guarded('Rejecting', () =>
        decideApproval(orchestration.orchestration_id, pending.approval_request_id, {
          actor_role: pending.required_role,
          actor_display_name: OPERATOR,
          decision: 'reject',
          reason,
        }),
      )
    },
    [guarded, orchestration],
  )

  const executeApproved = useCallback(async () => {
    if (orchestration?.current_state === 'approved') await executeAndVerify(orchestration)
  }, [executeAndVerify, orchestration])

  const verify = useCallback(async () => {
    if (!orchestration) return
    await guarded('Verifying', () => verifySynthetic(orchestration.orchestration_id))
  }, [guarded, orchestration])

  const rollback = useCallback(
    async (reason: string) => {
      if (!orchestration) return
      await guarded('Rolling back', () => rollbackSynthetic(orchestration.orchestration_id, reason))
    },
    [guarded, orchestration],
  )

  const setAutonomyMode = useCallback(async (mode: AutonomyMode) => {
    setAutonomyUpdating(true)
    setAutonomyError(null)
    try {
      setAutonomy(await putAutonomyMode(mode, OPERATOR, mode === 'autonomous'))
    } catch (reason) {
      setAutonomyError(toClientApiError(reason).message)
    } finally {
      setAutonomyUpdating(false)
    }
  }, [])

  const scenarioName =
    playback.scenarios.find((item) => item.scenario_id === playback.activeRun?.scenario_id)?.name ??
    null

  const stages = useMemo(
    () =>
      deriveWorkflowStages({
        run: playback.activeRun,
        scenarioName,
        starting: playback.starting,
        playbackState: playback.playbackState,
        currentEventIndex: playback.currentEventIndex,
        totalEventCount: playback.totalEventCount,
        detectionEnabled: playback.detectionEnabled,
        scoringStatus: playback.scoringStatus,
        assessments: playback.assessmentTimeline,
        correlationEnabled: playback.correlationEnabled,
        correlationStatus: playback.correlationStatus,
        incident: playback.currentIncidentCandidate,
        predictionEnabled: playback.predictionEnabled,
        predictionStatus: playback.predictionStatus,
        prediction: meaningfulPrediction(playback.predictionTimeline),
        autonomyMode: autonomy?.mode ?? null,
        workflowStatus: status,
        workflowError: error,
        result,
        orchestration,
        audit,
      }),
    [audit, autonomy?.mode, error, orchestration, playback, result, scenarioName, status],
  )
  const rail = useMemo(() => deriveRail(stages), [stages])

  const value = useMemo(
    () => ({
      session,
      autonomy,
      autonomyUpdating,
      setAutonomyMode,
      autoRun,
      setAutoRun,
      status,
      error,
      result,
      orchestration,
      audit,
      stages,
      rail,
      canRun,
      actionPending,
      runWorkflow,
      approve,
      reject,
      executeApproved,
      verify,
      rollback,
      refresh,
    }),
    [
      actionPending,
      approve,
      audit,
      autoRun,
      autonomy,
      autonomyUpdating,
      canRun,
      error,
      executeApproved,
      orchestration,
      rail,
      refresh,
      reject,
      result,
      rollback,
      runWorkflow,
      session,
      setAutonomyMode,
      stages,
      status,
      verify,
    ],
  )
  return (
    <AutonomyWorkflowContext.Provider value={value}>{children}</AutonomyWorkflowContext.Provider>
  )
}
