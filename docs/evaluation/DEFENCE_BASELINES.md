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
weighting, just a hardcoded lookup table on `scenario_id`. **Corrected**: this
mode previously executed through the full Phase 4 six-agent orchestration
pipeline, secretly giving the "dumb" baseline the benefit of Response
Planner/Impact Simulation/Safety Governor/Approval Router/Synthetic
Execution/Verification — see "Correction: no Phase 4 orchestration" below.

**Behavior:** matches `RULE_TABLE` purely against `experiment.scenario_id`
(plus one evidence check for the ingress-edge rule), resolves a target via
simple topology/evidence lookups, then — if the matched playbook (or its
safe-default fallback) is genuinely auto-eligible — calls
`synthetic_mutation_service.compute_mutation()` directly and persists its own
`EvaluationSyntheticActionRecord`. It never calls `orchestration_service`,
`blue_planning_service`, or `workflow_coordinator`.

**Isolation guarantee:** never calls `response_service.analyze()` (no
Defense-Score ranking), never calls `blue_planning_service.compare()` (no
Digital Twin what-if candidate comparison), and never calls
`orchestration_service`/`workflow_coordinator` (zero Phase 4
`AgentDecisionRecord`s, zero `ResponseOrchestrationRecord`).

**Approval-eligibility policy:** only ever executes a playbook whose
`DefensivePlaybook.automatic_eligibility` is `True` (equivalently,
`approval_tier == "automatic_candidate"` — confirmed consistent for every
playbook in `response_playbook_service.PLAYBOOKS`). If `RULE_TABLE`'s matched
playbook is not auto-eligible, it falls back to the documented safe default
(`increase-synthetic-monitoring`, itself auto-eligible). If even the fallback
is not auto-eligible, no safe response is executed at all — recorded
honestly as an `EvaluationSyntheticActionRecord` with `executed=False` and an
explanatory `note`, never a fabricated approval.

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
ranking, but no Digital Twin comparison of candidates. **Corrected**: this
mode previously executed through the full Phase 4 six-agent orchestration
pipeline, just like `rule_based` — see "Correction: no Phase 4 orchestration"
below.

**Behavior:** calls `response_service.analyze(session, run_id, model_id,
through_sequence, True, 5, False)` — the existing Defense-Score ranking
pipeline — then walks `analysis.recommendations` in rank order and executes
the FIRST one whose playbook is genuinely auto-eligible via
`synthetic_mutation_service.compute_mutation()` directly, persisting its own
`EvaluationSyntheticActionRecord`. If none of the ranked recommendations are
auto-eligible, no safe response is executed (recorded with `executed=False`).
This is a single-shot selection restricted to what an unattended baseline
could safely execute without a human — not the full ranking Agentic mode is
entitled to act on.

**Explicitly NOT used:** the Response Utility Score, Digital Twin what-if
comparison, or the six-agent Phase 4 pipeline
(`blue_planning_service.compare()`, `workflow_coordinator.run()`,
`orchestration_service`) — `MLAssistedDefenceStrategy`'s own docstring states
this directly: "Uses `response_service.analyze()`'s existing Defense-Score
ranking (no Response Utility Score, no Digital Twin what-if comparison — that
is the Agentic mode's job) and walks the ranked recommendations in order,
executing the FIRST one whose playbook is genuinely auto-eligible ...
never `orchestration_service`/`workflow_coordinator`."

`response_service.analyze()` itself still persists its own real
`ResponseAnalysisRecord`/`ResponseRecommendationRecord`/
`ResponseImpactSimulationRecord`s regardless of what this strategy does with
the result — that candidate-generation/ranking machinery is genuine
analytical work, not an agent decision, and is shared with the human-in-the-
loop demo paths elsewhere in this codebase.

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

## Correction: no Phase 4 orchestration for `rule_based`/`ml_assisted`

`rule_based` and `ml_assisted` are supposed to be simple, non-agentic
baselines — that is the entire point of comparing them against `agentic`.
They previously called `orchestration_service.create()`/`.execute()`/
`.verify()` (and even auto-approved pending approvals via an
"evaluation-engine" identity, a since-removed helper called
`_advance_to_terminal`), which internally runs ALL SIX of Phase 4's Blue
agents (Response Planner, Impact Simulation, Safety Governor, Approval
Router, Synthetic Execution, Verification) and persists an
`AgentDecisionRecord` for each — secretly giving the "dumb" baselines the
benefit of the full six-agent system and invalidating the comparison against
`agentic`.

Both strategies now call `app.services.synthetic_mutation_service
.compute_mutation()` directly — the same pure topology/playbook-spec
arithmetic `SyntheticExecutionAgent.mutation()` uses (Phase 4's agent is now
a thin wrapper around this shared primitive, extracted with zero behavior
change) — and persist their own lightweight, evaluation-only
`EvaluationSyntheticActionRecord` (`app/database/models.py`). This record is
deliberately NOT an `AgentDecisionRecord` and carries no `orchestration_id`:
`ExperimentRecord.evaluation_action_id` references it instead of
`ExperimentRecord.orchestration_id`, which stays `None` for these two modes.

**Status-transition consequence:** since neither mode ever produces a
`ResponseOrchestrationRecord`, neither ever passes through the `VERIFYING`
experiment status — their lifecycle is `CREATED → RUNNING_ATTACK →
DETECTING → RESPONDING → COMPLETED`, the same as `no_active_defence`. Only
`agentic` passes through `VERIFYING`.

**Metrics consequence** (`metrics_service.py`): `containment_success` is now
computed identically for every mode from a shared, stateless
`what_if_evidence_service.security_improved(evidence)` helper (also used by
`orchestration_agents.VerificationAgent`) — "did Attack Graph/Blast
Radius/critical-target reachability genuinely drop" — rather than reading
Phase 4's `verification_status`, which `rule_based`/`ml_assisted` no longer
produce. `verification_success` stays honestly `N/A` for these two modes:
"verification" specifically denotes Phase 4's dedicated post-execution
Verification Agent step, which by design never runs for them — this is
distinct from `containment_success`, which IS measured for every mode.
`approval_count`/`administrator_approval_count`/`analyst_approval_count` are
now genuinely `0` for these two modes (no approval gate exists to fake
anymore), and `rollback_required`/`rollback_success` stay `N/A` (no rollback
mechanism exists for a mode with no orchestration to roll back).

## Deliberately deferred: `SecurityGainEvidence`

None of the four strategies persist their own `security_gain_evidence_before
/after` on `StrategyOutcome`. The metrics stage
(`metrics_service.py::_security_metrics`) recomputes `SecurityGainEvidence`
independently and uniformly for all four modes — including
`no_active_defence`, which has no orchestration or synthetic action at
all — straight from `what_if_evidence_service`, using only the experiment's
`run_id`/`detection_model_id`/`through_sequence`. This keeps exactly one
methodology for "what was the real security gain", applied identically
across every mode.
