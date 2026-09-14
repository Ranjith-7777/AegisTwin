# The Four Defence Baselines

All four modes are dispatched from one interface
(`app/services/evaluation/strategies.py::get_strategy`) after identical
detection/correlation groundwork has already run
(`ExperimentService.create_and_run`). See ADR-010 for why this is a thin
dispatcher over the existing Phase 1-4 services rather than four duplicated
pipelines.

## 1. `no_active_defence` (control)

**Purpose:** the fairness baseline — "what would the numbers look like if
nobody responded at all?"

**Behavior:** `NoActiveDefenceStrategy.execute` returns immediately with a
single note. It never calls `response_service`, `blue_planning_service`, or
`orchestration_service` (`strategies.py`, class docstring, verbatim):

> Detection/correlation still ran as common groundwork ... but this strategy
> takes no defensive action at all: it never calls `response_service`,
> `blue_planning_service`, or `orchestration_service`.

No topology mutation happens, so `changed_node_ids`/`changed_edge_ids` are
always empty, `verification_status` is always `None`, and every
response/verification/rollback metric downstream is genuinely N/A (never a
fabricated 0).

## 2. `rule_based`

**Purpose:** "a dumb, deterministic baseline" — no ranking, no evidence
weighting, just a hardcoded lookup table on `scenario_id`.

**Behavior:** matches `RULE_TABLE` purely against `experiment.scenario_id`
(plus one evidence check for the ingress-edge rule), resolves a target via
simple topology/evidence lookups, constructs a minimal
`ResponseRecommendationRecord`/`ResponseImpactSimulationRecord` directly
(bypassing `response_service.analyze()`'s candidate generation/ranking
entirely), then executes through `orchestration_service` — the same
Approval Router/Safety Governor/Synthetic Execution/Verification path every
other acting mode uses.

**Isolation guarantee:** never calls `response_service.analyze()` (no
Defense-Score ranking) and never calls `blue_planning_service.compare()` (no
Digital Twin what-if candidate comparison).

**Full `RULE_TABLE`** (`app/services/evaluation/strategies.py`):

| rule_id | condition | playbook_id | reason |
|---|---|---|---|
| `RULE-DDOS-01` | `scenario_id == 'ddos-traffic-spike'` | `rate-limit-synthetic-gateway` | Volumetric scenario: apply a gateway rate limit regardless of evidence detail. |
| `RULE-INGRESS-01` | `scenario_id == 'leaked-api-credential' AND` an anomalous external-ingress edge is observed | `quarantine-synthetic-ingress-edge` | Leaked-credential scenario with an observed anomalous ingress edge: quarantine the attacker's own ingress route. |
| `RULE-CRED-01` | `scenario_id in ('credential-compromise', 'staged-compromise-demo', 'leaked-api-credential')` | `revoke-synthetic-sessions` | Credential-flavoured scenario: revoke the evidenced identity's sessions. |
| `RULE-WORKLOAD-01` | `scenario_id == 'suspicious-kubernetes-pod'` | `quarantine-synthetic-application` | Workload scenario: quarantine the suspicious pod. |
| `RULE-DEFAULT-01` | no match | `increase-synthetic-monitoring` | Safe default: no rule matched, so only observation is increased. |

Rule evaluation order matters: `RULE-INGRESS-01` is checked before
`RULE-CRED-01`, so `leaked-api-credential` with an observed ingress edge
takes the more specific ingress-quarantine rule; without that evidence it
falls through to the generic credential rule.

## 3. `ml_assisted`

**Purpose:** "the ranked-but-not-what-if-aware baseline" — real ML/evidence
ranking, but no Digital Twin comparison of candidates.

**Behavior:** calls `response_service.analyze(session, run_id, model_id,
through_sequence, True, 5, False)` — the existing Defense-Score ranking
pipeline — takes the single top-ranked recommendation
(`analysis.recommendations[0]`), and executes it through
`orchestration_service` directly.

**Explicitly NOT used:** the Response Utility Score, Digital Twin what-if
comparison, or the six-agent Phase 4 pipeline
(`blue_planning_service.compare()`, `workflow_coordinator.run()`) —
`MLAssistedDefenceStrategy`'s own docstring states this directly: "Uses
`response_service.analyze()`'s existing Defense-Score ranking (no Response
Utility Score, no Digital Twin what-if comparison — that is the Agentic
mode's job)."

## 4. `agentic`

**Purpose:** the real Phase 4 closed loop under evaluation.

**Behavior:** calls `workflow_coordinator.run(session, run_id, model_id,
incident_candidate_id, sequence, top_k=5)` — the production autonomous
workflow (Response Planner → Impact Simulation → Safety Governor → Approval
Router → Synthetic Execution → Verification, with automatic
policy-triggered rollback on failure per ADR-009). Global autonomy is
temporarily forced to `AutonomyMode.AUTONOMOUS` for the duration of the call
so the loop can reach automatic execution/verification, and the previous
mode is always restored in a `finally` block:

```python
previous_mode = autonomy_service.get(session).mode
try:
    autonomy_service.set_mode(session, AutonomyMode.AUTONOMOUS, "evaluation-engine")
    result = workflow_coordinator.run(session, run_id, model_id, incident_candidate_id, sequence, top_k=5)
finally:
    autonomy_service.set_mode(session, previous_mode, "evaluation-engine")
```

This is shared mutable global config — the class docstring notes explicitly
that "other concurrent code and tests must never observe it leaked", which
is why the restore is unconditional.

## Shared post-orchestration path (`rule_based`/`ml_assisted` only)

`_advance_to_terminal` auto-approves a pending human-approval gate on behalf
of the evaluation harness itself — never by silently changing autonomy mode
or bypassing the Safety Governor/Approval Router, both of which still ran
and made a real decision. This exists because `rule_based`/`ml_assisted` are
automated evaluation baselines, not the human-in-the-loop autonomy demo; the
`agentic` mode never needs this path since it is forced fully autonomous for
the run.

## Deliberately deferred: `SecurityGainEvidence`

None of the four strategies persist their own `security_gain_evidence_before
/after` on `StrategyOutcome`. `rule_based`/`ml_assisted` go through
`orchestration_service.execute()`/`.verify()`, which independently
recomputes real before/after Attack Graph/Blast Radius evidence via
`what_if_evidence_service`; the `agentic` mode's `WorkflowRunResult
.orchestration` carries the equivalent. The metrics stage
(`metrics_service.py::_security_metrics`) recomputes `SecurityGainEvidence`
independently and uniformly for all four modes — including
`no_active_defence`, which has no orchestration at all — straight from
`what_if_evidence_service`, using only the experiment's `run_id`/
`detection_model_id`/`through_sequence`. This keeps exactly one methodology
for "what was the real security gain", applied identically across every
mode.
