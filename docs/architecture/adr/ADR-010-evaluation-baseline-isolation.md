# ADR-010: Evaluation Baseline Isolation as a Thin Dispatcher Over Existing Services

## Status
Accepted. See "Addendum" below for a correction found and fixed during a
later Phase 5 research-validity pass — the rest of this ADR (the thin-
dispatcher shape, the shared post-hoc security-gain measurement) remains
accurate.

## Context

Phase 5 needed four defence-strategy baselines (`no_active_defence`,
`rule_based`, `ml_assisted`, `agentic`) that could be fairly compared
against one another. The obvious risk with "compare four defence
strategies" is building four semi-independent pipelines that quietly diverge
in how they detect, correlate, or measure security effect — at which point
a difference in the final score could be an artifact of pipeline drift
rather than a real difference in defence-mode effectiveness.

## Decision

`app/services/evaluation/experiment_service.py` runs one identical
groundwork path (scenario replay, canonical detection training/scoring,
correlation) for every experiment regardless of `defence_mode`, then
dispatches to exactly one of four `DefenceStrategy` implementations in
`app/services/evaluation/strategies.py`:

- `NoActiveDefenceStrategy` never calls `response_service`,
  `blue_planning_service`, or `orchestration_service` at all.
- `RuleBasedDefenceStrategy` matches a hardcoded `RULE_TABLE` on
  `scenario_id`, bypasses `response_service.analyze()`'s ranking entirely,
  and executes through `orchestration_service` directly.
- `MLAssistedDefenceStrategy` uses `response_service.analyze()`'s existing
  Defense-Score ranking (no Response Utility Score, no Digital Twin
  what-if comparison), takes the top recommendation, executes through
  `orchestration_service` directly.
- `AgenticDefenceStrategy` runs the real, unmodified
  `workflow_coordinator.run()` production path.

None of the four strategies compute their own `SecurityGainEvidence`.
Instead, `metrics_service.py::_security_metrics` recomputes it
independently and identically for all four modes at the measurement stage,
straight from `what_if_evidence_service`, using only the experiment's
`run_id`/`detection_model_id`/`through_sequence` and its real
`changed_node_ids`/`changed_edge_ids`. This guarantees exactly one
methodology for "what was the real security gain", applied uniformly.

## Isolation guarantees

- `no_active_defence` never calls `response_service`, `blue_planning_service`,
  or `orchestration_service`.
- `rule_based` never calls `response_service.analyze()`.
- `rule_based` and `ml_assisted` never call `blue_planning_service.compare()`
  or `workflow_coordinator.run()`.
- `agentic` runs the exact same production code path used outside
  evaluation, with global autonomy forced to `AUTONOMOUS` only for the
  duration of the call and restored via `finally` regardless of outcome.

## Fairness invariants

`scenario_id`, `seed`, `topology_version`, the canonical detection-training
configuration, and `CANONICAL_START_TIME`/`CANONICAL_PLAYBACK_SPEED` are
held fixed across every experiment (see
`docs/evaluation/EXPERIMENT_REPRODUCIBILITY.md`). Correlation runs
identically for all four modes, including `no_active_defence`, so that mode
still SEES the incident it chooses not to act on — this is what makes it a
fair control rather than a strawman that never even had the information
other modes had.

## Alternatives considered

1. **Four fully independent evaluation pipelines, each re-implementing its
   own detection/correlation/scoring.** Rejected: risks silent divergence
   between pipelines, and quadruples the surface area for a bug that would
   corrupt exactly one mode's comparability without being obviously
   detectable.
2. **A single unified "defence engine" parameterized by a strategy flag
   threaded through every internal call.** Rejected: this codebase's
   Phase 1-4 services (`response_service`, `orchestration_service`,
   `workflow_coordinator`) were not designed with a strategy-mode
   parameter, and retrofitting one risks introducing the same
   strategy-awareness into the scoring layer that ADR-011 explicitly rules
   out for `compute_score`. A thin dispatcher over the UNMODIFIED existing
   services is a smaller, more auditable surface.
3. **Let each strategy compute and report its own security-gain evidence.**
   Rejected: this codebase's strategies already have three different
   natural places evidence could originate (the impact simulation, the
   verification record, the workflow result) — deferring to one shared
   post-hoc measurement (`metrics_service.py`) instead of trusting each
   strategy's own internal bookkeeping avoids three subtly different
   "security gain" definitions.

## Consequences

- Positive: a bug or scoring skew found in one mode's baseline can only be
  a bug in that mode's own ~50-100 line `DefenceStrategy.execute`, or in
  the shared groundwork every mode goes through identically — never a
  quiet divergence in how "before/after" was measured.
- Positive: `no_active_defence` genuinely costs almost nothing to run
  (single early return), so it is cheap to include in every batch as a
  baseline.
- Negative: `rule_based`/`ml_assisted` need an evaluation-harness-only
  auto-approval shim (`_advance_to_terminal`) to reach a terminal state
  without a human in the loop — this is explicitly documented as a harness
  convenience, never a silent autonomy-mode change, but it does mean these
  two modes' human-approval-gate behavior is not identical to how they
  would run outside evaluation.

## Future reconsideration trigger

Revisit if a future phase adds a fifth defence strategy whose natural
implementation cannot cleanly reuse `orchestration_service`'s
execute/verify path (e.g. a strategy with genuinely different rollback
semantics) — at which point the shared `_advance_to_terminal` helper and
the uniform post-hoc `SecurityGainEvidence` recomputation should be
re-examined for whether they still apply cleanly.

## Addendum (Phase 5 research-validity correction pass): the isolation this
ADR describes was not actually in place

**What was wrong.** Despite this ADR's own "Isolation guarantees" section
stating `rule_based`/`ml_assisted` "never call `blue_planning_service.compare()`
or `workflow_coordinator.run()`," the implementation at the time still routed
both strategies through `orchestration_service.create()`/`.execute()`/
`.verify()` — which internally runs ALL SIX of Phase 4's Blue agents
(Response Planner, Impact Simulation, Safety Governor, Approval Router,
Synthetic Execution, Verification) and persists an `AgentDecisionRecord` for
each, plus an evaluation-harness shim that auto-approved any pending human
approval gate. The ADR's design intent was correct; the code had drifted
from it.

**Why it mattered.** This is precisely the failure mode ADR-010's own
"Context" section warns about — "a difference in the final score could be an
artifact of pipeline drift rather than a real difference in defence-mode
effectiveness" — except the drift was into the WORST possible case: the two
baselines meant to represent "no sophisticated multi-agent reasoning" were
silently borrowing that exact reasoning. Every comparison against `agentic`
was confounded for as long as this went uncorrected.

**What changed.** `RuleBasedDefenceStrategy`/`MLAssistedDefenceStrategy` now
call `synthetic_mutation_service.compute_mutation()` directly — the same
pure topology/playbook-spec arithmetic `SyntheticExecutionAgent.mutation()`
uses, extracted into a shared, evaluation-neutral primitive — and persist
their own lightweight `EvaluationSyntheticActionRecord`
(`app.database.models.EvaluationSyntheticActionRecord`), never an
`AgentDecisionRecord` and never a `ResponseOrchestrationRecord`. Approval
semantics are no longer faked: both strategies only execute a playbook that
is genuinely auto-eligible (`DefensivePlaybook.automatic_eligibility`),
falling back to a documented safe default or honestly recording
`executed=False` when nothing auto-eligible exists. Outcome measurement
remains unchanged in spirit — `security_improved()` (via
`what_if_evidence_service`) is still computed identically and post-hoc for
all four modes, per this ADR's original "Decision" section.

**Verification.** The corrected isolation was directly confirmed against the
real 80-experiment canonical matrix re-run: a full-matrix database query for
`AgentDecisionRecord`s tied to the 40 `rule_based`+`ml_assisted` canonical
experiments' `orchestration_id`s returned **zero** across the board (0/40),
while the 20 `agentic` canonical experiments show the expected six-agent
trace where the workflow actually reached execution (15/20; the remaining
5/20 — all `suspicious-kubernetes-pod`/`workload_service_compromise` — stop
honestly at 4 agents, Approval Router never granting automatic execution).
See `docs/evaluation/RESULTS.md`'s corrected-results section for the full
numbers, and `app/services/evaluation/strategies.py`'s module docstring for
the complete mechanism.
