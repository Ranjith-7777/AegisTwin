# ADR-006: Purple Team as a Pure Orchestrator Over the Existing Pipeline

## Status
Accepted — Phase 3.

## Context

Phase 3 required a reproducible Purple Team experiment runner
orchestrating the *existing* pipeline (simulation → detection →
correlation → prediction → optionally response/orchestration) "rather
than duplicating any detection/response logic," while strictly
distinguishing step outcomes and never conflating detection with
prevention. A fundamental architectural fact shapes what's possible
here: `simulation_service.SimulationRunService.create_run` generates a
scenario's entire telemetry timeline in one deterministic batch upfront
— it is not an interactive, step-by-step process that a mid-run Blue
action could influence.

## Decision

Build `purple_team_service.py` as a thin orchestrator that only calls
existing services in the already-established dependency order (each
service's own precondition checks enforce the order; the orchestrator
does not duplicate those checks) and reads back their persisted results
per scenario step. In particular:

1. **No new telemetry, detection, correlation, prediction, or response
   logic.** Every field on a `PurpleTeamStepResult` is read from an
   existing table (`TelemetryEventRecord`, `AnomalyAssessmentRecord`,
   `TechniqueObservationRecord`) or an existing static computation
   (`red_scenario_catalogue.iter_scenario_techniques`).
2. **`BLOCKED_SYNTHETIC` is sequence-bounded, not aspirational.** A step
   may only be classified `blocked_synthetic` if its sequence number is
   strictly greater than the sequence the winning response was analyzed
   through *and* that response's orchestration actually reached
   `verified` state. Given point (this ADR's context) that telemetry is
   generated once upfront and response analysis today always runs
   through the full event count, this condition is honestly documented
   as unreachable in the current architecture (see
   `docs/architecture/PURPLE_TEAM.md`) rather than faked by, e.g.,
   marking every step touching the recommended target as blocked
   regardless of timing (an earlier draft of this service did exactly
   that and was caught and fixed during implementation — see the
   sequence-bounding check in `_classify_outcome`).
3. **A synthetic approval actor, not new approval logic.** Most
   response recommendations require `analyst_approval` or
   `administrator_approval` before orchestration can execute. Rather
   than leaving `defense_enabled` experiments permanently stuck at
   `awaiting_*_approval` (which would make the mode nearly useless for
   demonstrating the full Blue response loop), the orchestrator calls
   the existing `orchestration_service.decide_approval` as an automated
   "purple-team-experiment" actor — the exact same API a human operator
   uses (see `tests/test_orchestration.py`'s `approve()` helper). This
   is not new approval logic; it is an automated caller of existing,
   unmodified approval logic.

## Alternatives considered

1. **Fabricate `blocked_synthetic` whenever a step's target matches a
   verified response's target, regardless of sequence.** Rejected (and
   caught during implementation, see point 2 above): this would violate
   the phase's explicit sequence-bounded causal-analysis requirement —
   a step that occurred *before* the response was even recommended
   cannot honestly be described as blocked by it.
2. **Build a second, interactive telemetry generator that can pause
   mid-scenario for a Blue decision.** Rejected as disproportionate for
   this phase and explicitly out of scope: it would mean replacing or
   forking `event_generator`, a core existing component, without the
   phase's required escalation for such a change. The current batch
   architecture's limitation is instead documented honestly.
3. **Require a human to manually approve every `defense_enabled`
   experiment through the existing orchestration UI before it can
   complete.** Rejected: this would make `run_experiment` an
   asynchronous, multi-request workflow instead of the single
   deterministic call every other pipeline stage in this codebase is,
   and would make the experiment non-reproducible in an automated test
   or demo run.

## Consequences

- Positive: `purple_team_service.py` has zero detection/response
  business logic to maintain or drift out of sync with the real
  pipeline — a change to how `correlation_service` computes evidence
  automatically flows through to Purple Team results with no changes
  needed here.
- Positive: `defense_enabled` experiments can demonstrate a genuine,
  fully-verified synthetic response (see
  `tests/test_purple_team.py::test_defense_enabled_experiment_may_create_and_execute_a_real_response`)
  without a human in the loop, while every recorded outcome remains
  traceable to a real orchestration state transition.
- Negative: `blocked_synthetic` cannot currently be observed in
  practice, which limits how visually compelling a `defense_enabled`
  demo's "contained" outcome can be. This is accepted as an honest
  limitation rather than worked around with fabricated data.

## Future reconsideration trigger

Revisit if a future phase introduces an interactive/step-by-step
scenario runner (letting a Blue decision genuinely precede and affect
later Red steps within the same run) — at which point
`blocked_synthetic`'s sequence-bounding condition would finally become
reachable, and the automated-approval-actor design here should be
reassessed against whatever new autonomy-level policy that phase
introduces.
