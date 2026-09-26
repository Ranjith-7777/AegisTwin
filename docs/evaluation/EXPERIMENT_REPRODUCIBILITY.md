# Experiment Reproducibility

## What's persisted for reproduction

Every `ExperimentRecord` carries, alongside its result:

- **Version fields:** `topology_version` (from `TOPOLOGY_VERSION`),
  `red_scenario_version` (`RED_SCENARIO_VERSION =
  "red-scenario-catalogue-v1"`), and — once scored, on the paired
  `ExperimentMetricRecord` — `metrics_version`
  (`"aegis-evaluation-metrics-v1"`), `mci_version` (`"aegis-mci-v1"`),
  `ars_version` (`"aegis-resilience-score-v1"`).
- **`seed`** — the deterministic RNG seed for the scenario replay.
- **`configuration_json`** — a full snapshot recorded at creation time,
  including `scenario_id`, `seed`, `defence_mode`, `top_k`,
  `through_sequence`, `label`, `notes`, `perturbation_id`,
  `perturbation_params`, and — critically — the canonical fixed constants
  themselves: `start_time` (`CANONICAL_START_TIME.isoformat()`),
  `playback_speed` (`CANONICAL_PLAYBACK_SPEED`), and `training_request`
  (`CANONICAL_TRAINING_REQUEST.model_dump(mode="json")`). Recording the
  canonical constants into every experiment's own configuration, rather
  than only relying on the module-level Python constant, means a future
  reader inspecting one experiment's `configuration_json` can always
  confirm which canonical timing/training configuration actually produced
  it — no need to cross-reference source code state at the time it ran.
- **`detection_model_id`** — which trained/scored detector produced the
  detection evidence (`DetectionTrainingService.train()` is idempotent/
  deterministic: it derives `model_id` from the dataset fingerprint and
  training parameters and returns the existing model unchanged if it
  already exists, so re-running the same canonical training request is
  cheap and safe). Real-outcome measurement (`metrics_service
  ._security_metrics`'s Attack Graph/Blast Radius evidence) always reads
  from this canonical identity, for every experiment, perturbed or not.
- **`perturbed_model_id`** — `None` for every unperturbed experiment
  (`perturbation_id is None`, the overwhelming majority). For a perturbed
  experiment, this is a SECOND, derived `DetectionModelRecord` identity
  (`perturbation_service.materialize_perturbed_model`) that shares the
  canonical model's exact trained pipeline/artifact but whose persisted
  `AnomalyAssessmentRecord`s genuinely omit the hidden events' real
  detection signal. `correlation_service.analyze()` and whichever defence
  strategy is dispatched are called with THIS identity, not the canonical
  one, so a perturbed experiment's actual defence DECISION - not just its
  reported score - is computed from the degraded evidence. See
  `app/services/evaluation/perturbation_service.py`'s module docstring for
  the full mechanism and why every event (hidden or visible) still gets a
  persisted assessment row under this identity.

## Why these constants must never vary between compared modes

`CANONICAL_START_TIME`, `CANONICAL_PLAYBACK_SPEED`, and
`CANONICAL_TRAINING_REQUEST` (`app/services/evaluation/
experiment_service.py`) are module-level constants, deliberately never
parameterized per experiment. If two experiments being compared used
different start times or replay speeds, differences in `time_to_*` metrics
could reflect nothing more than a different simulated clock offset rather
than a real difference in defence-mode effectiveness — a confound that
would make the whole comparison meaningless. If they used different
detection-model configurations, a difference in `detection_coverage` could
reflect a better/worse detector rather than a better/worse defence
strategy. Fixing these constants project-wide is what allows
`ComparisonService.check_fairness` to treat "same `scenario_id`, same
`seed`, same `topology_version`" as sufficient grounds for a paired
comparison, without also having to check timing/training parameters
per-pair — they are invariant everywhere by construction.

## "Re-run Experiment"

`POST /v1/evaluation/experiments/{experiment_id}/rerun`
(`app/api/routes/evaluation.py::rerun_experiment`) reads the original
experiment's `configuration_json` for `scenario_id`, `seed`, `defence_mode`,
`top_k`, `through_sequence`, builds a fresh `ExperimentCreate`, and calls
`experiment_service.create_and_run` — **this always creates a brand-new
`ExperimentRecord`** with a new `experiment_id`. The new record's
`rerun_of_experiment_id` is set to the original's `experiment_id`. The
original experiment is never touched, never overwritten, and never mutated
in any way by a re-run.

```python
rerun = experiment_service.create_and_run(session, request)
rerun.rerun_of_experiment_id = original.experiment_id
session.commit()
if rerun.status == ExperimentStatus.COMPLETED.value:
    evaluate_experiment(session, rerun.experiment_id)
```

Because the scenario/seed/topology/detection-training configuration is
identical and deterministic, a re-run of a `COMPLETED` experiment is
expected to reproduce closely comparable metrics — small variation can
still occur wherever the underlying pipeline itself is not perfectly
deterministic (e.g. wall-clock latency fields, or any non-deterministic
step in a downstream service), but the attack replay, detection groundwork,
and defence-strategy dispatch logic are all seeded/config-driven.

## Immutability of `COMPLETED` experiments

Nothing in the Phase 5 API ever mutates a `COMPLETED` experiment's
`ExperimentRecord` fields in place except the one-time transition into that
status itself and the always-safe, idempotent recomputation of its derived
`ExperimentMetricRecord`/`MissionHealthPointRecord`s (`_ensure_evaluated`
in `app/api/routes/evaluation.py` only computes metrics once, reading the
persisted record thereafter — it does not blindly recompute on every GET,
per spec Section 74: "derived metrics may be recomputed only with explicit
version/change semantics"). A `GET` never re-runs the attack or the defence
strategy; only the explicit `POST .../rerun` endpoint runs anything new,
and it always does so as a separate record. This means an experiment's
result, once completed and scored, is a durable, citable artifact — a
report or comparison built from it today will read the same values a year
from now, even if the scoring formulas themselves are later revised (a
formula revision would bump `metrics_version`/`ars_version`/`mci_version`
and only affect experiments scored after the change; `ComparisonService
.check_fairness` explicitly refuses to pair experiments scored under
mismatched versions).

## See also

`PHASE_5_EVALUATION_FRAMEWORK.md` for the fairness invariants these version
fields support; `RESULTS.md` for the canonical matrix these constants make
comparable.
