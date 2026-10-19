import { describe, expect, it } from 'vitest'

import {
  aggregateStatus,
  currentStage,
  deriveRail,
  deriveWorkflowStages,
  type StageId,
  type StageStatus,
} from '../lib/workflowStages'
import { explainSelection, primaryEffect } from '../lib/decision'
import { derivePosture } from '../lib/posture'
import { meaningfulPrediction } from '../lib/prediction'
import { routeForPath, sectionForPath } from '../lib/routes'
import {
  assessment,
  candidate,
  execution,
  incident,
  inputs,
  orchestration,
  result as workflowResult,
  run,
  snapshot,
  verification,
} from './fixtures/workflow'

function statuses(...args: Parameters<typeof inputs>): Record<StageId, StageStatus> {
  return Object.fromEntries(
    deriveWorkflowStages(inputs(...args)).map((stage) => [stage.id, stage.status]),
  ) as Record<StageId, StageStatus>
}

describe('workflow stage derivation', () => {
  it('has exactly the fourteen lifecycle stages in order', () => {
    expect(deriveWorkflowStages(inputs()).map((stage) => stage.id)).toEqual([
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
    ])
  })

  it('waits for everything before a run exists', () => {
    const result = statuses({ run: null, assessments: [], incident: null, prediction: null })
    expect(new Set(Object.values(result))).toEqual(new Set(['waiting']))
  })

  it('reports a running replay and a completed detection with anomalies', () => {
    const result = statuses({ playbackState: 'playing', currentEventIndex: 5 })
    expect(result.attack).toBe('completed')
    expect(result.telemetry).toBe('running')
    expect(result.detection).toBe('completed')
  })

  it('keeps an evidence-poor prediction running until the replay ends', () => {
    expect(statuses({ playbackState: 'playing', prediction: snapshot(0) }).prediction).toBe(
      'running',
    )
    expect(statuses({ playbackState: 'completed', prediction: snapshot(0) }).prediction).toBe(
      'warning',
    )
  })

  it('warns when a finished replay produced no anomaly', () => {
    expect(statuses({ assessments: [assessment(1, false)] }).detection).toBe('warning')
  })

  it('skips every Blue stage in observe mode and never claims execution', () => {
    const result = statuses({
      autonomyMode: 'observe',
      result: workflowResult('observe', null, null),
    })
    for (const id of ['response', 'what_if', 'policy', 'approval'] as const)
      expect(result[id]).toBe('skipped')
    expect(result.execution).toBe('waiting')
  })

  it('ranks but never orchestrates in recommend mode', () => {
    const result = statuses({
      autonomyMode: 'recommend',
      result: workflowResult('recommend', [candidate()], null),
    })
    expect(result.response).toBe('completed')
    expect(result.what_if).toBe('completed')
    expect(result.policy).toBe('completed')
    expect(result.approval).toBe('skipped')
    expect(result.execution).toBe('waiting')
  })

  it('shows an open human gate in approval-required mode', () => {
    const pending = orchestration('awaiting_analyst_approval', {
      approvals: [
        {
          approval_request_id: 'ap-1',
          plan_step_id: 's-1',
          required_role: 'analyst',
          approval_state: 'pending',
          requested_at: '2026-07-21T09:00:00Z',
          decided_at: null,
          decided_by: null,
          decision_reason: null,
          synthetic: true,
        },
      ],
    })
    const result = statuses({
      autonomyMode: 'approval_required',
      result: workflowResult('approval_required', [candidate()], pending),
      orchestration: pending,
    })
    expect(result.approval).toBe('awaiting')
    expect(result.execution).toBe('waiting')
    expect(currentStage(deriveWorkflowStages(inputs({ orchestration: pending })))?.id).toBe(
      'approval',
    )
  })

  it('completes the autonomous loop only from persisted execution and verification', () => {
    const verified = orchestration('verified', {
      executions: [execution],
      verifications: [verification],
    })
    const result = statuses({
      result: workflowResult('autonomous', [candidate()], verified),
      orchestration: verified,
      audit: {
        valid: true,
        event_count: 11,
        first_invalid_sequence: null,
        algorithm: 'SHA-256',
        synthetic: true,
      },
    })
    expect(result.approval).toBe('completed')
    expect(result.execution).toBe('completed')
    expect(result.verification).toBe('completed')
    expect(result.rollback).toBe('skipped')
    expect(result.twin).toBe('completed')
    expect(result.audit).toBe('completed')
  })

  it('shows rollback and a restored twin after a rollback', () => {
    const rolled = orchestration('synthetic_rollback_completed', {
      executions: [{ ...execution, execution_state: 'rolled_back_simulated' }],
      verifications: [verification],
      rollback: {
        rollback_id: 'rb',
        execution_id: 'x-1',
        reason: 'Operator-requested rollback',
        requested_by: 'Demo',
        state: 'synthetic_rollback_completed',
        restored_state_reference: 'pre',
        verification_summary: {},
        synthetic: true,
      },
    })
    const result = statuses({
      orchestration: rolled,
      result: workflowResult('autonomous', [candidate()], rolled),
    })
    expect(result.rollback).toBe('rolled_back')
    expect(result.twin).toBe('rolled_back')
  })

  it('blocks the policy stage when no candidate passes every policy', () => {
    const blocked = candidate({
      recommended: false,
      policy_pass: false,
      policy_failed_ids: ['POL-004'],
    })
    const result = statuses({ result: workflowResult('autonomous', [blocked], null) })
    expect(result.policy).toBe('blocked')
    expect(result.approval).toBe('blocked')
  })

  it('flags a broken audit chain as failed', () => {
    const verified = orchestration('verified', {
      executions: [execution],
      verifications: [verification],
    })
    expect(
      statuses({
        orchestration: verified,
        audit: {
          valid: false,
          event_count: 11,
          first_invalid_sequence: 4,
          algorithm: 'SHA-256',
          synthetic: true,
        },
      }).audit,
    ).toBe('failed')
  })
})

describe('rail aggregation', () => {
  it('prioritises failure, then human gates, then progress', () => {
    expect(aggregateStatus(['completed', 'failed', 'running'])).toBe('failed')
    expect(aggregateStatus(['completed', 'awaiting'])).toBe('awaiting')
    expect(aggregateStatus(['completed', 'skipped'])).toBe('completed')
    expect(aggregateStatus(['skipped', 'skipped'])).toBe('skipped')
    expect(aggregateStatus(['completed', 'waiting'])).toBe('waiting')
  })

  it('maps the fourteen stages onto the eight command-centre steps', () => {
    const rail = deriveRail(deriveWorkflowStages(inputs()))
    expect(rail.map((step) => step.label)).toEqual([
      'Red',
      'Detect',
      'Correlate',
      'Predict',
      'Decide',
      'Execute',
      'Verify',
      'Recover',
    ])
  })
})

describe('decision explanation', () => {
  it('explains the selection from measured what-if evidence only', () => {
    const selected = candidate()
    const runnerUp = candidate({
      recommendation_id: 'rec-2',
      playbook_name: 'Rate-limit the gateway',
      recommended: false,
      operational_impact: 'medium',
      utility_score: { ...selected.utility_score, total: 61.2 },
      security_gain_evidence: {
        ...selected.security_gain_evidence,
        attack_paths_after: 1,
        critical_targets_reachable_after: 1,
      },
    })
    const explanation = explainSelection([runnerUp, selected])
    expect(explanation?.headline).toContain("Quarantine the attacker's ingress route")
    expect(explanation?.headline).toContain('critical targets from 1 to 0')
    expect(explanation?.reasons.join(' ')).toContain('78.9 vs 61.2')
    expect(explanation?.runnerUp?.recommendation_id).toBe('rec-2')
  })

  it('names the failed policy of a stronger but disallowed alternative', () => {
    const selected = candidate()
    const disallowed = candidate({
      recommendation_id: 'rec-3',
      playbook_name: 'Isolate the database',
      recommended: false,
      policy_pass: false,
      policy_failed_ids: ['POL-006'],
      utility_score: { ...selected.utility_score, total: 90 },
    })
    expect(explainSelection([selected, disallowed])?.reasons.join(' ')).toContain('POL-006')
  })

  it('returns nothing when no plan was recommended', () => {
    expect(explainSelection([candidate({ recommended: false })])).toBeNull()
  })

  it('describes a no-gain plan honestly', () => {
    const evidence = candidate().security_gain_evidence
    expect(
      primaryEffect(
        candidate({
          security_gain_evidence: {
            ...evidence,
            attack_paths_after: 1,
            critical_targets_reachable_after: 1,
            blast_radius_reachable_after: 6,
          },
        }),
      ),
    ).toBe('adds defensive coverage without changing measured reachability')
  })
})

describe('posture and helpers', () => {
  const base = {
    run,
    playbackState: 'completed' as const,
    assessments: [assessment(5, true)],
    incident,
    orchestration: null,
    result: null,
  }

  it('is standby without a run and contained only after verification', () => {
    expect(derivePosture({ ...base, run: null }).label).toBe('Standby')
    expect(derivePosture({ ...base, playbackState: 'playing' }).label).toBe('Under attack')
    expect(derivePosture(base).label).toBe('Incident open')
    expect(
      derivePosture({
        ...base,
        orchestration: orchestration('synthetic_execution_completed', { executions: [execution] }),
      }).label,
    ).toBe('Verifying')
    expect(derivePosture({ ...base, orchestration: orchestration('verified') }).label).toBe(
      'Contained',
    )
  })

  it('keeps the last evidence-backed prediction after the run concludes', () => {
    expect(meaningfulPrediction([snapshot(2), snapshot(0)])?.hypotheses).toHaveLength(2)
    expect(meaningfulPrediction([snapshot(0)])?.hypotheses).toHaveLength(0)
    expect(meaningfulPrediction([])).toBeNull()
  })

  it('resolves nested routes to the most specific navigation entry', () => {
    expect(sectionForPath('/digital-twin/attack-paths')?.id).toBe('digital-twin')
    expect(routeForPath('/digital-twin/attack-paths')?.label).toBe('Attack Paths')
    expect(sectionForPath('/digital-twin')?.id).toBe('digital-twin')
    expect(sectionForPath('/evaluation/experiments/abc/report')?.id).toBe('reports')
    expect(sectionForPath('/evaluation/compare')?.id).toBe('reports')
    expect(routeForPath('/evaluation/compare')?.label).toBe('Strategy Comparison')
    expect(sectionForPath('/app')?.id).toBe('overview')
  })
})
