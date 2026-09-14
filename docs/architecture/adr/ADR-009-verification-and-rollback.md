# ADR-009: Dual-Check Verification Reusing the Pre-Execution Impact Simulation

## Status
Superseded in part — Phase 4 final correction pass. See "Addendum" below;
the rest of this ADR (two independent checks, automatic rollback
triggering, rollback attribution now further corrected in
`VERIFICATION_AND_ROLLBACK.md`) remains accurate.

## Context

Phase 3's `VerificationAgent.verify()` treated the mere existence of a
mutation (`changed_nodes` or `changed_edges` non-empty, or zero expected
edges) as verification success. Phase 4 explicitly required checking
BOTH security effect (path removed/reduced, critical target protected,
blast radius reduced) AND operational health (required relationships
remain, disruption threshold not exceeded) — stating a mutation existing
must never alone equal success — plus automatic rollback triggering on
verification failure.

## Decision

`VerificationAgent.verify()` now computes two independent boolean
checks, `security_effect_confirmed` and `operational_health_ok`, both
required for `"successful_simulation"`:

- `security_effect_confirmed` reuses the **already-computed**
  `ResponseImpactSimulationRecord` fields
  (`sensitive_assets_reachable_before/after`,
  `correlated_paths_interrupted`) from before execution — no new graph
  query runs at verification time. A playbook that made no security
  claim in the first place (`expected_relationships_affected == 0`) is
  vacuously confirmed rather than penalized.
- `operational_health_ok` compares the same record's
  `operational_disruption_score` against a fixed threshold (0.5).

`orchestration_service.verify()` then calls
`policy_service.evaluate_rollback_policy(verification_failed, reversible)`
and, when it returns `"fail"` (verification failed and the action is
reversible), calls `rollback()` itself automatically, persisting the
policy's own reason string as the rollback reason.

## Alternatives considered

1. **Recompute Attack Graph/Blast Radius against the real post-execution
   topology state at verification time.** Rejected: the persisted
   topology is never actually mutated by synthetic execution (Digital
   Twin state changes are recorded as audit evidence —
   `changed_node_ids`/`changed_edge_ids` — not applied to
   `topology_service`'s base data), so there is no "real post-execution
   graph" to query independently of the already-computed pre-execution
   simulation. Reusing that simulation's before/after fields is not a
   shortcut; it is the only data that actually represents "what this
   specific execution was expected to change."
2. **Require a human to manually decide whether to roll back after every
   failed verification.** Rejected for the AUTONOMOUS/self-healing loop
   specifically: the phase's flagship demo requires the loop to close on
   both the success path (auto-verify) and the failure path (auto-
   rollback) without a human in the loop when policy allows it; a
   human-required rollback would leave a failed, unreversed containment
   action live in the synthetic twin indefinitely if no one happened to
   check the console.
3. **A single combined pass/fail flag instead of two independent
   metrics.** Rejected per the explicit phase requirement and because a
   single flag would hide *which* dimension failed — a professor asking
   "why did this fail verification" needs to see security vs.
   operational separately, not a merged boolean.

## Consequences

- Positive: verification and rollback triggering are provably
  deterministic and side-effect-free at read time (both reuse persisted
  data, no new queries against the live topology), keeping this phase's
  performance bound tight (see the Phase 4 completion report,
  "Performance").
- Positive: `tests/test_verification_and_rollback.py` can construct
  every combination (security-only, operational-only, both, neither, no-
  claim) as pure unit tests of `verification_agent.verify()` without
  standing up a full orchestration each time, plus one integration test
  proving the automatic-rollback wiring end to end.
- Negative: because the check reuses the pre-execution simulation's
  numbers rather than an independent post-execution measurement, a
  scenario where the synthetic execution itself diverged from what the
  simulation predicted (e.g. `SyntheticExecutionAgent.mutation()` and
  the simulation disagreeing about which edges would change) would not
  be caught by this check alone — `metrics_json.correlated_paths_remaining`
  (`expected_edges - len(changed_edges)`, already existed pre-Phase-4)
  remains the signal for that specific divergence.

## Future reconsideration trigger

Revisit if a future phase introduces genuine post-execution telemetry
for synthetic actions (i.e. the twin's live state actually diverges
observably from its pre-execution snapshot in a way the existing
Digital Twin views would show) — at which point verification could
additionally compare live twin state against the pre-execution
simulation's prediction, not just check the prediction's own before/
after fields.

## Addendum (Phase 4 final correction pass): Alternative 1 was wrong

Alternative 1 above reasoned that "there is no real post-execution graph
to query independently" because synthetic execution never mutates the
persisted base topology. That reasoning conflated *mutating the base
topology* with *recomputing evidence against a hypothetical exclusion*
— the second is exactly the what-if technique `blue_planning_service.py`
already used for pre-execution candidate comparison
(`what_if_evidence_service.security_gain_evidence()`), and it applies
equally well at verification time by passing the **real, logged**
`execution.changed_edge_ids_json` as the exclusion set instead of a
candidate's predicted one. This was a genuine correctness gap the
project manager identified: verification was re-reading a prediction and
calling it "verified," never independently confirming what the executed
mutation actually did.

**Corrected decision**: `orchestration_service.verify()` now calls
`what_if_evidence_service.best_security_gain_evidence()` twice — once
with the pre-execution simulation's predicted `changed_edge_ids`
(`expected_evidence`) and once with the real execution's actual
`changed_edge_ids` (`actual_evidence`) — and `VerificationAgent.verify()`
bases `security_effect_confirmed` on `actual_evidence` alone. Both calls
reuse the identical shared module Response Planning uses; no graph
algorithm is duplicated, and the "Negative" consequence listed above (no
independent post-execution measurement) no longer applies. See
`VERIFICATION_AND_ROLLBACK.md` for the corrected formulas and
`tests/test_verification_and_rollback.py` for the regression proof.

This also resolved a second, related gap: the previous design's
operational-health check never modeled "did this action unintentionally
isolate an asset it wasn't meant to touch." A real, generic check
(`_bystander_isolated_assets()` — pure edge-set arithmetic over the
existing topology, no new graph algorithm) now covers this.
