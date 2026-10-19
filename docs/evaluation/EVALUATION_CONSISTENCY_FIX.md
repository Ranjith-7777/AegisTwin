# Evaluation ↔ Verification consistency fix (2026-10-07)

## Symptom

For `staged-compromise-demo` with seed 84, the `agentic` experiment's own
Verification Agent confirmed **attack paths 1 → 0**, so the run was contained
and verified. The evaluation metrics for that same experiment disagreed:

- `attack_path_reduction = 0`
- `critical_exposure_reduction = 0`
- `containment_success = False`
- ARS ≈ 41.6

`rule_based` runs whose action was an edge cut showed the same problem.

## Cause

There are two code paths that measure "how much attacker reach did the action
remove", and they did not measure it the same way.

**Blue planner and Verification Agent.** Both call
`what_if_evidence_service.best_security_gain_evidence(..., edge_source_asset_id)`.
For a relationship target (`source--destination`), this also evaluates from
the edge's **source** asset. That matters when the cut edge sits upstream of
the default anchor, as with the attacker's ingress route
`external-user-01--api-gateway-01`.

**`metrics_service._security_metrics`.** This called the same function
**without** the edge source. Its traversal therefore never crossed the cut
edge, and an edge cut always counted as zero reduction.

## Fix

`backend/app/services/evaluation/metrics_service.py` adds
`_edge_source_asset_id(session, experiment)`. It reads the executed action's
target from one of two places:

- the evaluation synthetic action, for baseline strategies;
- the orchestration's `SyntheticExecutionRecord`, for `agentic`.

It derives the source asset exactly as `blue_planning_service.compare()` does,
and passes it to `best_security_gain_evidence`. Nothing else changed: no
formula, weight or threshold was touched.

## Effect

| staged-compromise-demo / 84 | Before | After |
|---|---|---|
| agentic `attack_path_reduction` | 0.0 | 1.0 |
| agentic `containment_success` | False | True (agrees with verification) |
| agentic ARS | 41.6 | 66.1 |
| `no_active_defence` | unchanged (never credited) | unchanged |

`backend/tests/test_evaluation_verification_consistency.py` pins this:

- for agentic, the containment result equals the verification result;
- rule-based edge cuts are credited in the same way;
- `no_active_defence` is never credited.

Experiments that were persisted before this change keep their old metric rows.
To get corrected numbers, re-run them, or reset the demo database.

## Not changed: MCI

The Mission Continuity Index is still 0 for every strategy in the built-in
scenarios. Exposure saturates the eight-asset estate before a response lands,
and the responses land at the end of the replay. The original authors
documented this and pinned it with a test that asserts `{0.0}`. Redefining
MCI just to produce differentiated numbers would be fabricating a result, so
the UI shows a caveat next to MCI instead. See
[MISSION_CONTINUITY_INDEX.md](MISSION_CONTINUITY_INDEX.md).
