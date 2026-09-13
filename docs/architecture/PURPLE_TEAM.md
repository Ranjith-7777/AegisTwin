# Purple Team Experiments

`app/services/purple_team_service.py` runs one Red scenario through the
**existing** simulation → detection → correlation → prediction →
(optionally) response/orchestration pipeline and records what actually
happened at each step. It introduces no new detection, correlation,
prediction, or response logic of its own — every number in a
`PurpleTeamExperiment` traces back to a call into an already-approved
service and that service's own persisted result.

## Call sequence

For every experiment (`PurpleTeamService.run_experiment`):

1. `simulation_run_service.create_run` — creates or reuses the
   deterministic run for `(scenario_id, seed)`.
2. `detection_training_service.train(DetectionTrainingRequest())` — the
   default detector, reused (not retrained) across experiments via the
   existing `uuid5`-keyed model lookup.
3. `detection_scoring_service.score_run` — scores every event in the run.
4. `correlation_service.analyze` — may or may not produce an incident
   candidate, depending on whether the scenario's telemetry actually
   contains evidence (`normal-operations` legitimately produces none).
5. `prediction_service.analyze` — only called if step 4 produced an
   incident candidate (this is `prediction_service`'s own precondition).
6. In `defense_enabled` mode only, and only if step 4 produced an
   incident candidate: `response_service.analyze` →
   `orchestration_service.create` → (if a synthetic approval is
   required) `orchestration_service.decide_approval` → (if approved)
   `orchestration_service.execute` → (if execution completed)
   `orchestration_service.verify`. The approval step mirrors exactly
   what a human operator does through the existing orchestration API
   (see `tests/test_orchestration.py`'s `approve()` helper) — it is not
   new approval logic, just an automated actor exercising the existing
   deterministic approval-router agent's decision.
7. Per scenario step: read back the real `TelemetryEventRecord`,
   `AnomalyAssessmentRecord`, and `TechniqueObservationRecord`s at that
   step's sequence number, and the static, pre-computed expected
   technique from `red_scenario_catalogue.iter_scenario_techniques`
   (which mirrors `correlation_service._map`'s exact condition logic
   statically, so it can never disagree with what correlation would
   compute at runtime).

## Step outcome semantics

`RedStepOutcome` (`app/schemas/purple.py`) is a closed vocabulary.
**Detection is never treated as prevention** — a step being detected
(`PurpleTeamStepResult.detected`) is completely independent of its
`outcome`:

- `succeeded_synthetic` — the scenario step's own declared `outcome`
  field was `"success"`. This is read directly from the scenario's
  authored data, never re-derived from telemetry.
- `failed_precondition` — the scenario step's own declared outcome was
  anything else.
- `blocked_synthetic` — **only** assigned when all three hold: (a) the
  step's target asset matches the response recommendation's target
  asset, (b) orchestration for that recommendation actually reached
  `verified` state (real synthetic execution + verification, not merely
  "proposed"), and (c) the step's sequence number is **strictly
  greater** than the sequence the response was analyzed through. That
  third condition is a hard sequence-bounding rule: a later Blue action
  can never retroactively "block" evidence that already existed before
  it was recommended. Because a run's telemetry is generated once, in
  full, upfront (`simulation_service.SimulationRunService.create_run`),
  and today's response analysis always runs through the full event
  count, there is never a step whose sequence exceeds that point within
  the same run — so `blocked_synthetic` will not be observed in this
  phase. This is an honestly-documented limitation of the current
  single-batch-generation architecture (see ADR-006), not a bug: the
  classification logic is correct and would fire were its precondition
  ever met, e.g. by a future interactive/step-by-step scenario runner.
- `attempted` — a safe fallback when a step exists but no stronger
  classification applies.
- `skipped` — reserved for a future interactive runner; never assigned
  today.

## Metric definitions (`PurpleTeamSummary`)

- `detection_step_coverage` = (steps with `detected == True` among
  those with a non-null `expected_technique_id`) / (count of steps with
  a non-null `expected_technique_id`); `None` when no step has an
  expected technique (e.g. `normal-operations`).
- `response_recommendation_created` = any step has a non-null
  `response_recommendation_id`.
- `response_executed` = any step's `orchestration_state` is
  `completed_simulated` or `verified`.
- `final_outcome` = `"contained"` if any step is `blocked_synthetic`,
  else `"detected"` if any step was detected, else `"undetected"`.

## Attack Graph and Blast Radius integration

`PurpleTeamService._derive_security_context` runs after step evaluation
and calls the real `AttackGraphService`/`BlastRadiusService` — the same
services the standalone Digital Twin tabs use, never a duplicate. It
never claims an asset was compromised merely because it is statically
reachable; two distinct notions are kept separate:

* **OBSERVED / REACHED** (`PurpleTeamSummary.critical_assets_reached`,
  `attack_path_context.path_type == "observed"`) — derived from
  `topology_path_service.run_state(...).anomalous_observed_asset_ids`,
  i.e. real telemetry evidence that anomaly detection actually flagged
  during this run. `critical_assets_reached` is the subset of that set
  with `criticality in {high, critical}`.
* **AT RISK / REACHABLE** (`blast_radius_context.critical_assets_at_risk`,
  `.reachable_count`, `.trust_zones_reached`) — a `BlastRadiusService`
  estimate, always a reachability claim, never an "actually happened"
  claim, per `docs/architecture/BLAST_RADIUS.md`.

Concretely: `attack_path_context` is the real top-ranked path (`max_paths=1`)
from the scenario's structured `initial_access_point` to its
`high_value_objective` (see `app/schemas/red_scenario.py`) —
`path_type=observed` (evidence-bound, run-scoped) when the run actually
produced anomalous-observed evidence, honestly falling back to
`path_type=potential` (no run/model passed) when it did not, rather than
fabricating observed evidence that doesn't exist. `blast_radius_context`
is rooted at the real anomalous-observed asset set when non-empty
(queried in `evidence_bound` mode, which is always internally consistent
since that same set is what defines the evidence), falling back to the
scenario's `initial_access_point` in `hypothetical` mode when no
anomalies were observed at all (e.g. `normal-operations`). Both calls
pass the experiment id as `correlation_id` so their published events
(`attack.path.discovered`, `blast_radius.assessed`) correlate with this
experiment's own event stream.

## Idempotency

`experiment_id = uuid5(NAMESPACE, f"{scenario_id}:{mode}:{seed}")`,
matching this codebase's standard deterministic-id convention. Calling
`run_experiment` again with the same `(scenario_id, mode, seed)` after a
prior run reached `status == "completed"` returns the persisted result
without re-running the pipeline. A prior `failed` attempt is retried
(existing step rows are deleted and rebuilt) rather than treated as
final.

## API

- `GET /api/v1/purple-team/scenarios` — the static, pre-computed MITRE
  summary for every built-in scenario.
- `POST /api/v1/purple-team/experiments` — runs (or returns the
  cached result for) one experiment.
- `GET /api/v1/purple-team/experiments` / `/{experiment_id}` — list /
  fetch persisted experiments.

## Events

`purple.experiment.started` and `purple.experiment.completed`
(`PurpleExperimentStartedPayload` / `PurpleExperimentCompletedPayload`)
bracket each run; `purple.step.completed`
(`PurpleStepCompletedPayload`) and the Red-side
`red.step.attempted` / `red.step.completed` (`RedStepPayload`) are
published per step — see `docs/architecture/EVENT_MODEL.md`.
