# Verification and Rollback

## A mutation existing is never, by itself, success

Before Phase 4, `VerificationAgent.verify()` computed
`applied = bool(changed_nodes or changed_edges) or expected_edges == 0`
and treated `applied` as the entire verification outcome — the mere
fact that *something* changed was "success." The first Phase 4 pass
replaced this with two independent checks, but initially read them from
the **pre-execution** `ResponseImpactSimulationRecord`'s predicted
before/after fields — which does not independently verify what actually
happened. The final correction pass fixes this: verification now
independently recomputes the **ACTUAL post-execution synthetic state**
via the real Attack Graph/Blast Radius engines and compares it against
an **EXPECTED** result computed the identical way, both reusing
`what_if_evidence_service` — no graph algorithm is duplicated.

```python
# app/services/orchestration_service.py::verify()
anchors, has_evidence = what_if_evidence_service.anchor_asset_ids(...)
expected_evidence = what_if_evidence_service.best_security_gain_evidence(
    ..., exclude_edge_ids=frozenset(simulation.changed_edge_ids_json), ...
)
actual_evidence = what_if_evidence_service.best_security_gain_evidence(
    ..., exclude_edge_ids=frozenset(execution.changed_edge_ids_json), ...
)
bystander_isolated = self._bystander_isolated_assets(
    execution.target_id, execution.changed_edge_ids_json
)
status, metrics = verification_agent.verify(
    execution.changed_node_ids_json, execution.changed_edge_ids_json,
    simulation.expected_relationships_affected,
    expected_evidence, actual_evidence, bystander_isolated,
)
```

`simulation.changed_edge_ids_json` (what the plan *predicted* it would
change) and `execution.changed_edge_ids_json` (what the
`SyntheticExecutionAgent` *actually* logged as changed) are usually
identical for a normal run, but verification computes both independently
so a genuine divergence between plan and execution would be caught, not
assumed away.

## IMPROVED is not the same as VERIFIED AGAINST EXPECTED OBJECTIVE

A second correction (found by independent PM audit) applies here: the
first pass's `security_effect_confirmed` only checked that the actual
result *improved* over the actual before-state — `actual_after <
actual_before` on any metric. That is a strictly weaker claim than "the
plan's promised containment objective was met." Example: `before=2`,
the plan *expected* `after=0` (eliminate the path entirely), but the
*actual* executed result was `after=1`. That is a real improvement
(2→1) — and the old check would have called it verified — but the
attacker still has a path the plan promised to close. This must fail.

```python
def _objective_met(expected_before, expected_after, actual_after) -> tuple[bool, bool]:
    # A metric is only "applicable" if the plan itself claimed an
    # improvement for it - a metric the plan never promised to move can
    # never create an artificial failure.
    applicable = expected_after < expected_before
    met = (not applicable) or (actual_after <= expected_after)
    return applicable, met

mutation_applied = bool(changed_nodes or changed_edges) or expected_edges == 0
no_security_claim = expected_edges == 0

# IMPROVED: some genuine improvement over the actual before-state, on any
# of the three metrics. Necessary but NOT sufficient.
security_improved = (
    actual_evidence.attack_paths_after < actual_evidence.attack_paths_before
    or actual_evidence.blast_radius_reachable_after < actual_evidence.blast_radius_reachable_before
    or actual_evidence.critical_targets_reachable_after < actual_evidence.critical_targets_reachable_before
)

# VERIFIED AGAINST EXPECTED OBJECTIVE: for every metric the plan itself
# claimed it would improve, did the actual result meet or outperform the
# expected (simulated) result?
attack_path_applicable, attack_path_objective_met = _objective_met(
    expected_evidence.attack_paths_before, expected_evidence.attack_paths_after,
    actual_evidence.attack_paths_after)
critical_target_applicable, critical_target_objective_met = _objective_met(
    expected_evidence.critical_targets_reachable_before, expected_evidence.critical_targets_reachable_after,
    actual_evidence.critical_targets_reachable_after)
blast_radius_applicable, blast_radius_objective_met = _objective_met(
    expected_evidence.blast_radius_reachable_before, expected_evidence.blast_radius_reachable_after,
    actual_evidence.blast_radius_reachable_after)
expected_containment_met = (
    attack_path_objective_met and critical_target_objective_met and blast_radius_objective_met
)

# BOTH required: some genuine improvement happened, AND every metric the
# plan claimed to improve actually met its expected objective.
security_effect_confirmed = no_security_claim or (security_improved and expected_containment_met)

operational_disruption_score = len(changed_edges) / len(topology_service.edges(True))
critical_connectivity_preserved = not bystander_isolated_asset_ids
operational_health_ok = (
    operational_disruption_score <= OPERATIONAL_DISRUPTION_THRESHOLD  # 0.5
    and critical_connectivity_preserved
)
status = "successful_simulation" if (
    mutation_applied and security_effect_confirmed and operational_health_ok
) else "unsuccessful_simulation"
```

Worked examples (all regression-tested,
`tests/test_verification_and_rollback.py`):

| before | expected after | actual after | improved? | objective met? | result |
|---|---|---|---|---|---|
| 2 | 0 | 1 | yes (2→1) | no (1 > 0) | **FAILS** (partial containment, objective missed) |
| 2 | 1 | 1 | yes (2→1) | yes (1 ≤ 1) | succeeds (if operational health passes) |
| 2 | 1 | 0 | yes (2→0) | yes (0 ≤ 1, outperformed) | succeeds |

A metric the plan never claimed to improve (`expected_after ==
expected_before`) is never `applicable`, so it can never create an
artificial failure — this is why an observe-only action
(`expected_edges == 0`) retains its vacuous-pass semantics regardless of
these objective checks (`no_security_claim` short-circuits first), and
why a plan that only claimed to improve attack paths (not blast radius
or critical targets) is judged solely on the attack-path objective.

`metrics_json` exposes `security_improved`, `expected_containment_met`,
`attack_path_objective_met`, `critical_target_objective_met`,
`blast_radius_objective_met`, and their `*_objective_applicable`
counterparts — a professor asking "why did this fail" can see exactly
which claimed objective was missed, not a single merged boolean.

- **Operational health** has two independent components:
  1. **Disruption ratio** — the real executed edge-removal count over
     total topology edges, within a bounded threshold.
  2. **Critical connectivity preserved** — a real check
     (`_bystander_isolated_assets()`) over the existing synthetic
     topology's edge set: did removing these edges fully cut off any
     asset *other than* the plan's own intended target (both endpoints
     of an edge-restriction target are the intended effect, not
     bystanders)? Pure edge-set arithmetic, no Attack Graph/Blast Radius
     traversal duplicated.

`metrics_json` on the persisted `ResponseVerificationRecord` includes
`expected_attack_paths_after`, `actual_attack_paths_after`,
`expected_blast_radius_after`, `actual_blast_radius_after`,
`expected_critical_targets_after`, `actual_critical_targets_after`,
`security_effect_confirmed`, `operational_health_ok`,
`critical_connectivity_preserved`, and `bystander_isolated_asset_ids` —
all explicit, all real, and rendered in the frontend
(`VerificationPage.tsx`).

This is a regression-tested behavior (`tests/test_verification_and_rollback.py`):
a real mutation whose actual post-execution state shows no security
improvement is `unsuccessful_simulation` even though the plan predicted
one; a real mutation that improved but fell short of the plan's own
expected objective fails (tests `A`, `D`, `E`); a result that meets or
outperforms the expected objective succeeds (tests `B`, `C`); an
observe-only action retains its vacuous-pass semantics (test `F`); a
real mutation that unintentionally isolates a bystander asset fails
regardless of its security effect; excessive disruption ratio fails;
only every applicable check together is `successful_simulation`.

## Verification persists a real AgentDecisionRecord

`orchestration_service.verify()` now calls `self._decision()` for the
Verification Agent — the same mechanism the other 5 Blue agents already
used — with `decision_type="verification"`, `decision` set to the
verification status, warnings naming which check failed, and
`next_agent=None` (it is always the terminal agent). A complete
orchestration's trace now shows all 6 Blue agents in exact causal order:
Response Planner → Impact Simulation → Safety Governor → Approval Router
→ Synthetic Execution → Verification (`tests/test_agent_registry.py::
test_complete_orchestration_trace_shows_the_exact_six_blue_agent_order`).

## Automatic rollback

`orchestration_service.verify()` calls
`policy_service.evaluate_rollback_policy(verification_failed, reversible)`
immediately after persisting a failed verification. When that policy's
result is `"fail"` (meaning: verification failed **and** the action is
reversible — POL-007, see `POLICY_ENGINE.md`), `verify()` automatically
calls `rollback(..., automatic=True)`, passing the policy's own reason
string as the rollback reason and `"Verification Agent (automatic
policy-triggered rollback)"` as the requester. **A human no longer has
to notice a failed verification and manually trigger rollback** — this
closes the self-healing loop's failure path the same way its success
path already closed automatically.

If the action is *not* reversible, POL-007 returns `"pass"` ("rollback
is not possible; this must be surfaced to a human operator") and no
automatic rollback is attempted — `orchestration_service.rollback()`
itself independently refuses a non-reversible execution
(`ROLLBACK_NOT_REVERSIBLE`, unchanged from Phase 3), so this is a
double-enforced invariant, not a single point of failure.

### Rollback audit attribution is truthful (Phase 4 final correction pass)

`rollback()` previously always recorded the audit actor as `"human"` /
`"demo-operator"`, even when the rollback was triggered automatically by
the Verification Agent's policy check — an untruthful audit trail.
`rollback()` now takes an `automatic: bool = False` parameter; when
`True` (only ever passed from `verify()`'s auto-trigger path), the audit
event's `actor_type`/`actor_id` are `"simulation_agent"` /
`"verification-agent"`, and the canonical payload includes
`"automatic": true`. A manual `POST .../rollback` call still records
`"human"` / `"demo-operator"` with `"automatic": false`. The existing
tamper-evident hash chain (`AuditEventRecord.event_hash`, chained via
`previous_event_hash`) is unaffected — attribution is just another field
in the same canonical payload the hash already covers.

Verified end-to-end
(`tests/test_verification_and_rollback.py::test_failed_verification_automatically_triggers_rollback_for_a_reversible_action`):
inflating the *actual* executed mutation's `changed_edge_ids` (not the
prediction) past the operational-disruption threshold, then calling
`verify()` once, results in `current_state == "synthetic_rollback_completed"`,
a `RollbackView.reason` beginning with `"Automatic rollback:"`, and an
audit event with `actor_type == "simulation_agent"` and
`actor_id == "verification-agent"` — with no separate call to
`rollback()` in the test. A companion test
(`test_manual_rollback_still_attributes_to_the_human_actor`) confirms a
normal, human-initiated rollback is unaffected.

## What rollback still does (unchanged from Phase 3)

`rollback()` is idempotent (a second call for the same orchestration
returns the existing `RollbackRecord`), requires the orchestration to be
in `verified` or `rollback_recommended` state, requires the execution to
be marked `reversible`, and persists `reason`, `requested_by`,
`restored_state_reference`, and a `verification_summary_json`. No real
cloud rollback occurs — this restores only the persisted synthetic
execution/twin state, exactly as execution itself only ever mutated
that same synthetic state.
