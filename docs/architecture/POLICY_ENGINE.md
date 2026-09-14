# Policy Engine

`app/services/policy_service.py` is a small, deterministic, inspectable
policy-as-code catalogue and evaluator — deliberately **not** OPA/
Gatekeeper. The Phase 4 spec is explicit that a dedicated policy engine
would be disproportionate for this modular monolith's needs, and every
policy here is a plain Python function returning typed Pydantic results;
there is no policy DSL, no external process, and no network call.

## Every decision reports policy_id / result / reason — never a hidden boolean

`PolicyEvaluation` (`app/schemas/policy.py`) always carries `policy_id`,
`policy_name`, `result: "pass" | "fail" | "not_applicable"`, and a
human-readable `reason`. `evaluate_response_policies()` returns a
`PolicyEvaluationResult` with the full list of evaluations plus
`overall_pass` and `failed_policy_ids` — a caller never has to guess
*why* a plan was blocked, and the professor-facing UI
(`PoliciesPage.tsx`, and the Safety Governor's warnings in
`VerificationPage.tsx`) surfaces the same reasons the backend computed.

## The catalogue (`GET /api/v1/policies`)

| ID | Name | Applies to | Effect |
|---|---|---|---|
| POL-001 | Synthetic-only targets | Every candidate plan | Blocks execution if the recommendation is not marked synthetic |
| POL-002 | Prohibited playbooks never execute | Every candidate plan | Blocks execution if the playbook's approval tier is `prohibited` |
| POL-003 | Autonomous execution requires reversibility | Autonomous mode only | Blocks automatic execution if the playbook is not reversible |
| POL-004 | Maximum allowed operational impact for automation | Autonomous mode only | Blocks automatic execution if declared impact exceeds `medium` |
| POL-005 | Maximum allowed automatic blast radius | Autonomous mode only | Blocks automatic execution if blast radius is broader than a single asset/identity/relationship |
| POL-006 | Critical data-store isolation requires administrator approval | Database/object-storage targets, high/critical criticality | Blocks automatic execution unless the playbook's own tier is already `administrator_approval` |
| POL-007 | Failed verification requires rollback where reversible | Post-execution verification | Triggers automatic rollback when verification fails and the action is reversible |

POL-001 and POL-002 are evaluated for **every** candidate regardless of
autonomy mode — a non-synthetic or catalogue-prohibited action is never
permitted, full stop. POL-003 through POL-006 are only meaningfully
evaluated when `autonomy_mode == "autonomous"`; in every other mode they
report `not_applicable` with the reason `"Autonomy mode is '<mode>', not
autonomous."` — this is itself a real, reportable evaluation, not a
silently skipped check. POL-007 is evaluated separately, once, at
verification time (`evaluate_rollback_policy()`), not as part of the
per-candidate response-policy list.

## Where policies are actually called

- `blue_planning_service.compare()` calls `evaluate_response_policies()`
  once per candidate to compute `CandidatePlanAssessment.policy_pass` /
  `policy_failed_ids` — a policy-failing candidate is never marked
  `recommended` (see `BLUE_RESPONSE_PLANNING.md`).
- `SafetyGovernorAgent.decide()` (`orchestration_agents.py`) calls the
  same function on the real orchestration path, with the real target's
  criticality/asset type looked up from `topology_service`, and attaches
  failed-policy reasons to its `AgentResult.warnings`.
- `orchestration_service.verify()` calls `evaluate_rollback_policy()`
  after a failed verification and automatically calls `rollback()` when
  the result is `"fail"` (meaning: verification failed and the action is
  reversible) — see `VERIFICATION_AND_ROLLBACK.md`.

## Constants (the actual thresholds)

```python
AUTONOMOUS_MAX_OPERATIONAL_IMPACT = "medium"
AUTONOMOUS_ELIGIBLE_BLAST_RADII = {"single_asset", "single_identity", "single_relationship"}
CRITICAL_TARGET_ASSET_TYPES = {"database", "object_storage"}
```

These are module-level constants, not database rows — changing an
automation threshold today means changing code (and the tests that pin
it), which is a deliberate choice for a security-relevant limit: it
should require a code review, not a runtime config edit.

## Determinism

`policy_service` has no hidden state and makes no I/O; the same inputs
always produce the same `PolicyEvaluationResult`
(`tests/test_policy_engine.py::test_policy_evaluation_is_deterministic`).
