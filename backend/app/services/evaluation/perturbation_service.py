"""Phase 5 - PM spec Section 38: PARTIAL-OBSERVABILITY ROBUSTNESS TEST.

Implements ONE deterministic perturbation mode: hide a fixed, deterministic
fraction of a run's non-critical (LOW/MEDIUM severity) telemetry events from
detection scoring, to test whether defence performance collapses under
slightly degraded observability. Per spec: "Do not change the underlying
attack" - this module NEVER mutates a persisted `TelemetryEventRecord`. It
only ever computes a *read-side* set of event ids to disregard.

## Why "hide" (not "delay")

The spec allows either "hide / delay a defined fraction of non-critical
telemetry events". Hiding is implemented here because:

1. It requires no new ordering/re-sequencing concept. Delay would need to
   shift an event's *effective* sequence position later, which risks
   colliding with the `through_sequence_number` ordinal-position convention
   documented in `metrics_service.py`'s module docstring and relied on
   everywhere else in this codebase (recommendations, orchestrations, impact
   simulations). Hiding sidesteps that risk entirely - a hidden event simply
   never contributes a detection, its ordinal position is irrelevant.
2. It is the more literal reading of "degraded observability": the defender
   genuinely never sees the evidence, rather than seeing it late.

## Why this operates at metrics-read time, not at `score_run` persistence
   time (an important deviation from the most literal reading of the spec)

`ExperimentService.create_and_run` derives `simulation_run_id` and
`detection_model_id` deterministically from
`(scenario_id, seed, start_time, playback_speed)` and the canonical training
request respectively (see `simulation_service.SimulationRunService
.create_run` and `detection_training_service`). That means a baseline
experiment and a perturbed experiment for the SAME scenario/seed/mode share
the exact SAME `simulation_run_id` and `model_id` - and therefore the exact
same underlying `AnomalyAssessmentRecord` rows
(`assessment_id = uuid5(model_id:event_id)`, one row per event, cached by
`DetectionScoringService.score_run`'s `existing`/`force_rescore` check).

If this module tried to make `score_run` skip PERSISTING assessments for
hidden events, the very first experiment (whichever of the pair runs first)
would leave that shared run's assessment set permanently incomplete, and the
SECOND experiment (baseline or perturbed, whichever runs second) would see
`existing > 0` and skip scoring entirely - silently inheriting the first
experiment's partial, perturbation-tainted assessment set. That would
corrupt the OTHER experiment's results, violating the "never affects any
other experiment" requirement.

So the hiding is instead applied purely when THIS experiment's own metrics
are computed (`metrics_service.EvaluationMetricsService._detection_metrics`/
`_first_detection_time`, `mission_continuity_service
.MissionContinuityService._detection_sequence`): those call sites read this
experiment's `hidden_event_ids` (persisted on `ExperimentRecord
.configuration_json`, computed once by `apply_perturbation` below and never
recomputed differently) and simply disregard any `AnomalyAssessmentRecord`
whose `event_id` is in that set, as if the detector had never scored it.
The underlying `AnomalyAssessmentRecord` rows themselves are untouched and
fully shared/cached as before - scoring behaviour for every OTHER
(unperturbed) experiment is completely unaffected.

Scope note: this affects the DETECTION/METRICS layer only - detection
coverage, false-positive stats, first-detection timing (and everything
downstream of those: MCI, ARS). It does not propagate into
`correlation_service`'s incident-candidate formation or the response/
orchestration strategies, which read from the same shared, run-cached
`AnomalyAssessmentRecord` table and are out of scope for "Keep it simple and
synthetic" per the spec - making the perturbation change actual defence
BEHAVIOUR (not just its measured detection performance) would require
threading per-experiment evidence filtering through correlation and every
strategy, a materially larger and riskier change than this deliverable
calls for.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ExperimentRecord, TelemetryEventRecord
from app.schemas.telemetry import Severity
from app.services.evaluation.metrics_service import GROUND_TRUTH_SEVERITIES

PARTIAL_OBSERVABILITY_PERTURBATION_ID = "partial-observability-v1"

DEFAULT_HIDDEN_FRACTION = 0.3

# The configuration_json keys this module writes onto ExperimentRecord, for
# consistent lookups everywhere (experiment_service.py write side;
# metrics_service.py/mission_continuity_service.py read side).
HIDDEN_EVENT_IDS_KEY = "hidden_event_ids"
HIDDEN_EVENT_COUNT_KEY = "hidden_event_count"

# "Non-critical" per the spec's own framing: every severity that is NOT a
# ground-truth attack-step severity (reusing metrics_service.py's own
# GROUND_TRUTH_SEVERITIES constant/distinction, per instructions, rather than
# inventing a new one).
_NON_CRITICAL_SEVERITY_VALUES = frozenset(severity.value for severity in Severity) - frozenset(
    severity.value for severity in GROUND_TRUTH_SEVERITIES
)


def apply_perturbation(
    session: Session,
    run_id: str,
    perturbation_id: str | None,
    perturbation_params: dict[str, object] | None,
) -> frozenset[str]:
    """Returns the set of event_ids to be HIDDEN from detection scoring for
    this experiment. Deterministic given (run_id, perturbation_params) - the
    same experiment re-run with the same perturbation config hides the SAME
    events every time (no randomness beyond what the run itself already
    deterministically seeded). Returns an empty frozenset if
    `perturbation_id` is None or unrecognised (no perturbation = no change,
    always the default for the other three defence-mode isolation tests and
    the canonical matrix).

    Deterministic selection rule (for `PARTIAL_OBSERVABILITY_PERTURBATION_ID`):
    1. Read this run's `TelemetryEventRecord`s, filtered to severity NOT IN
       `GROUND_TRUTH_SEVERITIES` (i.e. LOW/MEDIUM/INFORMATIONAL - "non-
       critical" per the spec's own framing) - HIGH/CRITICAL ground-truth
       attack-step events are NEVER eligible to be hidden.
    2. Sort the eligible event ids lexicographically (a stable, arbitrary-
       but-reproducible total order - event ids are UUIDs with no
       inherent temporal meaning of their own, so any deterministic order
       is as good as any other; sorting by id keeps this independent of
       query plan / row order).
    3. Compute `n_hidden = round(hidden_fraction * len(eligible))`.
    4. Walk the sorted list with a fixed stride of
       `len(eligible) / n_hidden` and take the floor index at each step
       (`floor(0*stride), floor(1*stride), floor(2*stride), ...`), which
       spreads the hidden events evenly across the sorted id space rather
       than always clustering at the front. This is pure arithmetic on
       already-sorted, already-deterministic input - no `random` module
       used anywhere.
    """

    if perturbation_id != PARTIAL_OBSERVABILITY_PERTURBATION_ID:
        return frozenset()

    params = perturbation_params or {}
    raw_fraction = params.get("hidden_fraction", DEFAULT_HIDDEN_FRACTION)
    try:
        hidden_fraction = float(raw_fraction)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        hidden_fraction = DEFAULT_HIDDEN_FRACTION
    hidden_fraction = max(0.0, min(1.0, hidden_fraction))

    rows = session.execute(
        select(TelemetryEventRecord.event_id, TelemetryEventRecord.severity).where(
            TelemetryEventRecord.simulation_run_id == run_id
        )
    ).all()
    eligible = sorted(
        event_id for event_id, severity in rows if severity in _NON_CRITICAL_SEVERITY_VALUES
    )

    n_hidden = round(hidden_fraction * len(eligible))
    if n_hidden <= 0 or not eligible:
        return frozenset()
    if n_hidden >= len(eligible):
        return frozenset(eligible)

    stride = len(eligible) / n_hidden
    selected_indices = sorted({int(i * stride) for i in range(n_hidden)})
    return frozenset(eligible[i] for i in selected_indices)


def hidden_event_ids_for_experiment(experiment: ExperimentRecord) -> frozenset[str]:
    """Reads back the hidden-event-id set this experiment was persisted
    with (see `experiment_service.create_and_run`). Empty for every
    unperturbed experiment - i.e. every experiment created before this
    feature existed, and every experiment with `perturbation_id=None`."""

    raw = experiment.configuration_json.get(HIDDEN_EVENT_IDS_KEY)
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(str(event_id) for event_id in raw)
