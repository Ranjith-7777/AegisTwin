# Verification and Rollback

## A mutation existing is never, by itself, success

Before Phase 4, `VerificationAgent.verify()` computed
`applied = bool(changed_nodes or changed_edges) or expected_edges == 0`
and treated `applied` as the entire verification outcome — the mere
fact that *something* changed was "success." Phase 4 replaces this with
two **independent**, explicitly reported checks that must both hold:

```python
mutation_applied = bool(changed_nodes or changed_edges) or expected_edges == 0
no_security_claim = expected_edges == 0
security_effect_confirmed = no_security_claim or (
    sensitive_assets_reachable_after < sensitive_assets_reachable_before
    or correlated_paths_interrupted > 0
)
operational_health_ok = operational_disruption_score <= OPERATIONAL_DISRUPTION_THRESHOLD  # 0.5

status = "successful_simulation" if (
    mutation_applied and security_effect_confirmed and operational_health_ok
) else "unsuccessful_simulation"
```

- **Security effect**: did reachability to sensitive assets actually
  decrease, or was a correlated attack path actually interrupted? An
  observe-only playbook that made no security claim in the first place
  (`expected_edges == 0`, e.g. `increase-synthetic-monitoring`) is never
  penalized for lacking an effect it never promised.
- **Operational health**: is the resulting operational disruption within
  a bounded threshold? A containment action that technically "worked"
  but broke too much is not a successful response.

Both metrics are already-computed fields on the `ResponseImpactSimulationRecord`
for the selected plan — **no new graph recomputation happens at
verification time**; the check reuses the exact evidence the Response
Planner/Impact Simulation Agent already produced before execution.
`metrics_json` on the persisted `ResponseVerificationRecord` now
includes `security_effect_confirmed` and `operational_health_ok`
explicitly, and the frontend (`VerificationPage.tsx`) renders both.

This is a regression-tested behavior
(`tests/test_verification_and_rollback.py`):
a real mutation with neither check passing is `unsuccessful_simulation`;
a real mutation with a security effect but excessive operational
disruption is still `unsuccessful_simulation`; only both together is
`successful_simulation`.

## Automatic rollback

`orchestration_service.verify()` now calls
`policy_service.evaluate_rollback_policy(verification_failed, reversible)`
immediately after persisting a failed verification. When that policy's
result is `"fail"` (meaning: verification failed **and** the action is
reversible — POL-007, see `POLICY_ENGINE.md`), `verify()` automatically
calls `rollback()` itself, passing the policy's own reason string
(`f"Automatic rollback: {rollback_policy.reason}"`) as the rollback
reason and `"Verification Agent (automatic policy-triggered rollback)"`
as the requester. **A human no longer has to notice a failed
verification and manually trigger rollback** — this closes the
self-healing loop's failure path the same way its success path already
closed automatically.

If the action is *not* reversible, POL-007 returns `"pass"` ("rollback
is not possible; this must be surfaced to a human operator") and no
automatic rollback is attempted — `orchestration_service.rollback()`
itself independently refuses a non-reversible execution
(`ROLLBACK_NOT_REVERSIBLE`, unchanged from Phase 3), so this is a
double-enforced invariant, not a single point of failure.

Verified end-to-end
(`tests/test_verification_and_rollback.py::test_failed_verification_automatically_triggers_rollback_for_a_reversible_action`):
degrading a persisted simulation's `operational_disruption_score` past
the threshold after a real execution, then calling `verify()` once,
results in `current_state == "synthetic_rollback_completed"` and a
`RollbackView.reason` beginning with `"Automatic rollback:"` — with no
separate call to `rollback()` in the test.

## What rollback still does (unchanged from Phase 3)

`rollback()` is idempotent (a second call for the same orchestration
returns the existing `RollbackRecord`), requires the orchestration to be
in `verified` or `rollback_recommended` state, requires the execution to
be marked `reversible`, and persists `reason`, `requested_by`,
`restored_state_reference`, and a `verification_summary_json`. No real
cloud rollback occurs — this restores only the persisted synthetic
execution/twin state, exactly as execution itself only ever mutated
that same synthetic state.
