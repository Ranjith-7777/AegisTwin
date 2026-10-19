# Workflow Replay Consistency and Mission Continuity Index - Findings

Date: 2026-10-13. Both items come from the final completion pass (Phase 3).

## A. Identical replay showed an impossible lifecycle - FIXED

**Symptom.** Replaying the same scenario and seed showed two things at once:
Execute "completed" while Decide was still "waiting", and an empty candidate
list.

**Root cause.** Simulation runs are deterministic: the same scenario, seed,
start and speed give the same run id. A second replay therefore reuses a run
that already has a persisted ranked comparison and orchestration. The console
restored only the orchestration (`listOrchestrations`), never the comparison,
so the "Decide" stage had nothing to show.

**Fix.**

- Backend: `WorkflowCoordinator.restore()` rebuilds the whole workflow result
  from stored records only, without re-planning or re-executing. It returns the
  comparison at the orchestration's evidence horizon, plus the orchestration.
  It is served by `GET /api/v1/workflow/runs/{run_id}/state?model_id=` (viewer
  role; 404 `WORKFLOW_STATE_NOT_FOUND` when nothing is recorded). The result
  carries `restored: true`.
- Frontend: `AutonomyWorkflowProvider` restores through that endpoint. It keeps
  the restored result hidden until the replay reaches the comparison's
  `through_sequence_number`, so a response never appears before the evidence it
  answers. It also does not auto-run again when a restored result exists.

**Evidence.**

- `backend/tests/test_workflow_state_restore.py` (4 tests): 404 before any run;
  the comparison is restored in recommend mode; comparison and execution are
  restored together and consistently in autonomous mode; restoring creates no
  records.
- `frontend/src/test/WorkflowState.test.tsx` (4 tests).
- Browser check on the dev stack:
  - At 5/12 events, Decide and Execute both show "waiting".
  - After the replay, Decide shows "5 candidates ranked · selected Quarantine
    the attacker's ingress route", consistent with Execute and Verify
    "completed".
  - The orchestration count stayed at 16, so the replay restored the stored
    result and executed nothing.

## B. Mission Continuity Index is 0.0 - EXPLAINED, NOT "FIXED"

The MCI arithmetic is correct. `MCI = trapezoidal AUC of mission health over
the experiment horizon ÷ horizon`, in `mission_continuity_service.py`. The zero
comes from the inputs. Nothing was changed to produce a non-zero number.

Measured on the real pipeline (seed 84, temporary database):

| Scenario | Start hour | Events flagged anomalous | MCI (all four modes) |
|---|---|---|---|
| staged-compromise-demo | 00:00 (canonical) | 12 / 12 | 0.0 |
| staged-compromise-demo | 09:00 (probe) | 9 / 12 (benign steps 1, 3, 4 included) | 0.0 |
| leaked-api-credential | 00:00 | 8 / 8 | 0.0 |
| leaked-api-credential | 09:00 | 6 / 8 | 0.0 |

The persisted curve is always `H=1 at t=0 → H=0 at t=0 → H=0 at the horizon`.
Four causes compound:

1. **Detection false positives on benign prefix steps.** At sequence 1 the
   anchors are `external-user-01` and `api-gateway-01`. Their blast radius covers
   all 13 assets, so health is 0 from the first event.
2. **Time-of-day confound.** In `detection_dataset_service.py`, normal
   training runs start at 08:00–16:00, but synthetic *attack* evaluation runs
   start at 00:00–04:00 (`seed % 5`). Experiments and purple-team runs replay at
   00:00 (`CANONICAL_START_TIME`). That contradicts the staged scenario's own
   `office_hours: true` metadata and makes every event look off-hours.
   Moving the start to 09:00 alone does **not** change MCI. It does show that
   the synthetic detection metrics are partly helped by hour-of-day.
3. **Single-shot response at the horizon.** Experiments decide with
   `through_sequence=None`, i.e. after the last event, so no post-response
   interval exists to credit.
4. **Chokepoint containment.** The only auto-eligible playbooks cut the sole
   ingress edge or the gateway. That disconnects every asset from the entry
   point, so health stays 0 even after containment.

`tests/test_mission_continuity_horizon.py` already asserts the real `{0.0}`,
and `test_recovery_credits_healthy_interval_and_faster_response_scores_higher`
shows the MCI machinery does credit earlier recovery when the inputs allow it.

**Recommended follow-up (not done; changes every published synthetic metric,
so it needs an explicit decision):**

- Give attack and normal synthetic runs the same hour distribution, and set
  canonical experiment starts within office hours.
- Run experiments online: let each strategy respond at the incident-confirmation
  sequence, not after the full run.
- Add a non-chokepoint containment playbook, such as isolating the compromised
  pod or revoking a credential, so containment can restore health.
