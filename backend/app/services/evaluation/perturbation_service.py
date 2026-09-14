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

## Corrected mechanism: a real, isolated "perturbed model identity" - not a
   metrics-only read-side filter (this is a deviation from an earlier
   revision of this module, which only filtered metrics; that revision is
   documented at the bottom of this docstring for context)

`correlation_service.analyze()`, `response_service.analyze()` and
`workflow_coordinator.run()` all scope every piece of evidence they read
(`AnomalyAssessmentRecord`, and everything derived from it) by
`(simulation_run_id, model_id)`. That partitioning is exploited directly:
instead of filtering hidden events out AFTER detection/correlation/response
have already made their decision from the full, unperturbed evidence set,
`ExperimentService.create_and_run` now materializes a SECOND, derived
`DetectionModelRecord` - the "perturbed model identity" - via
`materialize_perturbed_model()` below, and scores this run's events under
THAT identity via `score_visible_events()`. The derived identity shares the
exact same trained pipeline/artifact as the canonical model (same model
VERSION, same weights - no retraining), so a visible event's score is
bit-for-bit identical to what it would have gotten under the canonical
model (`DetectionScoringService.score_events` is a pure per-event function
of the artifact's fixed baselines - it does not depend on which other
events are present in the same scoring batch). A hidden event instead gets
a neutral, evidence-inert placeholder assessment (see "Why every event still
gets a persisted row" below).

`ExperimentService.create_and_run` then passes this PERTURBED model_id -
not the canonical one - to `correlation_service.analyze()` and to the
defence-strategy dispatch (`get_strategy(...).execute(...)`). Because those
services were already `model_id`-scoped, this makes the hidden evidence
genuinely invisible to incident formation, response-recommendation ranking,
and Agentic planning, with ZERO changes required in `correlation_service.py`,
`response_service.py`, `blue_planning_service.py`, or
`workflow_coordinator_service.py`.

## Why every event still gets a persisted row under the perturbed identity
   (a hidden event is neutralized, not literally absent as a table row)

Both `CorrelationService.analyze()` and `ResponseService.analyze()` contain a
hard completeness invariant: `correlation_service.analyze()` raises
`ASSESSMENTS_INCOMPLETE` unless `AnomalyAssessmentRecord` count for
`(run_id, model_id)` exactly equals this run's total (unfiltered) event
count, and `response_service.analyze()` raises `RESPONSE_ASSESSMENTS_REQUIRED`
under the equivalent per-sequence check. Ground truth (`TelemetryEventRecord`)
is - correctly, per spec - never filtered by run_id, so both checks compare
against the FULL event count regardless of which model_id is passed. Making
hidden events literally absent from `AnomalyAssessmentRecord` under the
perturbed identity would therefore make every perturbed experiment fail
these checks immediately - and the task's own constraint is that neither of
those two services may be modified.

So instead, every event - hidden or visible - gets exactly one
`AnomalyAssessmentRecord` under the perturbed model_id, preserving the same
1..N `sequence_number` ordinal as the canonical scoring (required for
`through_sequence_number` semantics to remain meaningful). A HIDDEN event's
row is a neutral placeholder: `classification=NORMAL`, `anomaly_score=0.0`,
empty `contributing_signals_json`, and `component_scores_json` containing
only the `PERTURBATION_HIDDEN_MARKER` key (see below) - i.e. it can never
itself be classified anomalous, never contributes to
`CorrelationService`'s `anomaly_evidence` score component, and is
distinguishable from a genuinely-scored row by inspection. This means the
literal `SELECT COUNT(*)` of `AnomalyAssessmentRecord` under the perturbed
identity equals the canonical run's total event count (an unavoidable
consequence of the invariants above) - the tests in
`test_robustness_perturbation.py` instead compare the count of
NON-neutralized ("informative") assessments, which IS strictly smaller for a
perturbed experiment, since that is what is actually available as evidence
to `response_service.analyze()`/`workflow_coordinator.run()`.

One known, honestly-documented residual gap: `CorrelationService._map()`
maps ATT&CK techniques directly from raw `TelemetryEvent` content
(`event.failed_attempts`, `event.metadata`, ...), independent of
`AnomalyAssessmentRecord`/`model_id` entirely - it runs unconditionally over
every one of this run's events, including hidden ones. A hidden event that
happens to match one of `CorrelationService._map()`'s rules therefore still
produces a `TechniqueObservationRecord` and can still enter
`CorrelationService.analyze()`'s `evidence_events`
(`event.event_id in observation_by_event`) even though its anomaly
assessment is neutralized. This is a real, structural limitation of
respecting the "zero changes to `correlation_service.py`" constraint, not an
oversight - see the module docstring of `test_robustness_perturbation.py`
for the concrete investigation of how often this actually matters in
practice for the "non-critical" (LOW/MEDIUM) severities eligible to be
hidden.

## Why the CANONICAL model identity is untouched, and canonical/unperturbed
   experiments are byte-for-byte unchanged

`ExperimentService.create_and_run` still trains/scores the canonical model
exactly as before for every experiment (perturbed or not) - this remains the
one true "real world" evidence source real-outcome measurement
(`metrics_service.py`'s `_security_metrics` Attack Graph/Blast Radius via
`what_if_evidence_service`) reads from, via `ExperimentRecord
.detection_model_id`, which is NEVER the perturbed identity. Materializing
and scoring the perturbed identity is a strictly ADDITIONAL step, gated
entirely on `request.perturbation_id is not None`; for an unperturbed
experiment, none of this module's new functions are even called, so
`ExperimentRecord.perturbed_model_id` stays `None` and every other code path
is identical to before this change.

## Prior revision (context only - superseded by the above)

An earlier revision of this module applied the hiding purely when THIS
experiment's own metrics were computed
(`metrics_service.EvaluationMetricsService._detection_metrics`/
`_first_detection_time`, `mission_continuity_service
.MissionContinuityService._detection_sequence`), never touching detection
scoring/persistence or propagating into `correlation_service`/response
strategies at all. That was flagged as a research-validity bug: it meant a
perturbed experiment's DEFENCE DECISION was computed from the exact same
full evidence as the unperturbed baseline, and only the final reported
SCORE differed - not a real robustness test. `metrics_service.py`'s and
`mission_continuity_service.py`'s hidden-event-id filtering (reading
`hidden_event_ids_for_experiment`/`_hidden_event_ids_for_experiment`) is
retained as a belt-and-suspenders check on the CANONICAL model's detection
metrics (which, per the above, are still computed from the canonical
identity, not the perturbed one) - it is redundant with the perturbed
identity's own naturally-smaller informative-assessment set for
"defender-observed" style metrics, but harmless and left in place rather
than risk a wider edit to already-passing metrics code for this deliverable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    AnomalyAssessmentRecord,
    DetectionModelRecord,
    ExperimentRecord,
    TelemetryEventRecord,
)
from app.schemas.detection import Classification, RunScoringResult
from app.schemas.telemetry import Severity
from app.services.detection_scoring_service import ScoreTuple, detection_scoring_service
from app.services.detection_training_service import detection_training_service
from app.services.evaluation.metrics_service import GROUND_TRUTH_SEVERITIES
from app.services.telemetry_service import telemetry_service

PARTIAL_OBSERVABILITY_PERTURBATION_ID = "partial-observability-v1"

DEFAULT_HIDDEN_FRACTION = 0.3

# The configuration_json keys this module writes onto ExperimentRecord, for
# consistent lookups everywhere (experiment_service.py write side;
# metrics_service.py/mission_continuity_service.py read side).
HIDDEN_EVENT_IDS_KEY = "hidden_event_ids"
HIDDEN_EVENT_COUNT_KEY = "hidden_event_count"

# Namespace for deriving a perturbed model identity from
# (base_model_id, perturbation_id, perturbation_params) - see
# `perturbed_model_id()` below. Distinct from `DetectionTrainingService
# .MODEL_NAMESPACE` since this is a derived identity, not a trained one.
PERTURBED_MODEL_NAMESPACE = UUID("6f6a9e0a-6a5b-4e9a-9a4a-6b6b7b6b7b6b")

# The single key written into a hidden event's placeholder
# `AnomalyAssessmentRecord.component_scores_json` under a perturbed model
# identity - see module docstring, "Why every event still gets a persisted
# row". Never present on a genuinely-scored (visible) assessment row, so
# `component_scores_json.get(PERTURBATION_HIDDEN_MARKER)` reliably
# distinguishes a neutralized placeholder from real evidence.
PERTURBATION_HIDDEN_MARKER = "perturbation_hidden"

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


def perturbed_model_id(
    base_model_id: str, perturbation_id: str, perturbation_params: dict[str, object]
) -> str:
    """Deterministic derived model_id for a given (base model, perturbation
    config) pair - `uuid5(base_model_id + perturbation_id + sorted params)`.
    Two experiments with the SAME base model and the SAME perturbation
    config (e.g. the same `hidden_fraction`) always resolve to the same
    derived identity (correct de-duplication/idempotency); two experiments
    with a genuinely different perturbation config always resolve to
    different identities (never collide)."""

    normalized_params = ":".join(
        f"{key}={perturbation_params[key]!r}" for key in sorted(perturbation_params)
    )
    return str(
        uuid5(
            PERTURBED_MODEL_NAMESPACE,
            f"{base_model_id}:{perturbation_id}:{normalized_params}",
        )
    )


def materialize_perturbed_model(
    session: Session,
    base_model_id: str,
    perturbation_id: str,
    perturbation_params: dict[str, object],
) -> str:
    """Ensures a `DetectionModelRecord` exists under
    `perturbed_model_id(...)`, cloning every field from the base record
    except `model_id` itself and pointing at the SAME `artifact_path` (same
    trained sklearn pipeline - no retraining, same model VERSION, per the
    "same model version and underlying telemetry" requirement). Idempotent:
    if the derived record already exists, returns its id unchanged without
    touching it again. Returns the derived model_id."""

    derived_id = perturbed_model_id(base_model_id, perturbation_id, perturbation_params)
    existing = session.get(DetectionModelRecord, derived_id)
    if existing is not None:
        return derived_id

    base = detection_training_service.get_record(session, base_model_id)
    session.add(
        DetectionModelRecord(
            model_id=derived_id,
            model_type=base.model_type,
            model_version=base.model_version,
            feature_schema_version=base.feature_schema_version,
            calibration_version=base.calibration_version,
            calibration_method=base.calibration_method,
            artifact_path=base.artifact_path,
            configuration_json={
                **base.configuration_json,
                "derived_from_model_id": base_model_id,
                "perturbation_id": perturbation_id,
                "perturbation_params": perturbation_params,
            },
            dataset_fingerprint=base.dataset_fingerprint,
            random_state=base.random_state,
            target_false_positive_rate=base.target_false_positive_rate,
            calibrated_threshold=base.calibrated_threshold,
            threshold_percentile=base.threshold_percentile,
            training_event_count=base.training_event_count,
            validation_event_count=base.validation_event_count,
            created_at=datetime.now(UTC),
            synthetic=True,
        )
    )
    session.flush()
    return derived_id


def score_visible_events(
    session: Session,
    run_id: str,
    perturbed_model_id_value: str,
    hidden_event_ids: frozenset[str],
) -> RunScoringResult:
    """Scores this run's events under `perturbed_model_id_value`: visible
    events (`event_id not in hidden_event_ids`) get a REAL score via
    `DetectionScoringService.score_events` (same pipeline/artifact as the
    canonical model - bit-for-bit identical to what they would score under
    the canonical model_id, since scoring is a pure per-event function of
    the artifact's fixed baselines). Hidden events get a neutral placeholder
    assessment instead (`classification=NORMAL`, zero scores, empty
    signals, `component_scores_json={PERTURBATION_HIDDEN_MARKER: 1.0}`) -
    see the module docstring for why every event still needs a row.

    Every event (hidden or visible) gets exactly one persisted row, numbered
    1..N in the SAME order as `telemetry_service.list_run_events` (the same
    ordinal every other `sequence_number`/`through_sequence_number` in this
    codebase uses), so `correlation_service.analyze()`'s and
    `response_service.analyze()`'s existing completeness invariants hold
    unmodified.

    Idempotent: if this run is already fully scored under
    `perturbed_model_id_value`, returns the existing result without
    re-scoring or duplicating rows (mirrors `DetectionScoringService
    .score_run`'s own `existing`/`force_rescore` pattern; a different
    `perturbed_model_id_value` per (base_model, perturbation_config) pair
    means different runs of the SAME perturbation config naturally dedupe
    correctly here, and different perturbation CONFIGS get genuinely
    different identities, never colliding - see `perturbed_model_id()`)."""

    events = telemetry_service.list_run_events(session, run_id)
    existing_count = int(
        session.scalar(
            select(func.count())
            .select_from(AnomalyAssessmentRecord)
            .where(
                AnomalyAssessmentRecord.model_id == perturbed_model_id_value,
                AnomalyAssessmentRecord.simulation_run_id == run_id,
            )
        )
        or 0
    )
    if events and existing_count == len(events):
        anomalous_count = int(
            session.scalar(
                select(func.count())
                .select_from(AnomalyAssessmentRecord)
                .where(
                    AnomalyAssessmentRecord.model_id == perturbed_model_id_value,
                    AnomalyAssessmentRecord.simulation_run_id == run_id,
                    AnomalyAssessmentRecord.classification == Classification.ANOMALOUS.value,
                )
            )
            or 0
        )
        return RunScoringResult(
            model_id=perturbed_model_id_value,
            simulation_run_id=run_id,
            assessment_count=existing_count,
            anomalous_count=anomalous_count,
            force_rescore=False,
            synthetic=True,
        )

    artifact = detection_scoring_service.load_artifact(session, perturbed_model_id_value)
    visible_events = [event for event in events if event.event_id not in hidden_event_ids]
    visible_scored = {
        tup[0].event_id: tup
        for tup in detection_scoring_service.score_events(artifact, visible_events)
    }
    scored: list[ScoreTuple] = []
    for event in events:
        if event.event_id in hidden_event_ids:
            scored.append(
                (event, 0.0, 0.0, Classification.NORMAL, [], {PERTURBATION_HIDDEN_MARKER: 1.0})
            )
        else:
            scored.append(visible_scored[event.event_id])

    return detection_scoring_service._persist_scores(
        session,
        perturbed_model_id_value,
        run_id,
        artifact.calibrated_threshold,
        scored,
        force_rescore=False,
        publish_event=False,
    )


def informative_assessment_count(session: Session, run_id: str, model_id: str) -> int:
    """Count of `AnomalyAssessmentRecord`s under `(run_id, model_id)` that
    are NOT a perturbation-neutralized placeholder - i.e. real, informative
    evidence available to `response_service.analyze()`/
    `workflow_coordinator.run()`. Equal to the plain row count for the
    canonical model identity (which never has neutralized rows) and equal to
    the plain row count minus the hidden-event count for a perturbed
    identity. Used by tests to prove the perturbed identity's usable
    evidence set is strictly smaller, without relying on a raw
    `COUNT(*)` that - per the module docstring - is necessarily equal to the
    canonical count for both identities."""

    # Filtered in Python rather than via a JSON-containment query: the
    # generic SQLAlchemy `JSON` column type used for `component_scores_json`
    # does not portably support `.contains()` across this codebase's
    # supported backends (notably SQLite, used in tests), so this reads the
    # (small, per-run) rows back and inspects the marker directly.
    rows = session.scalars(
        select(AnomalyAssessmentRecord.component_scores_json).where(
            AnomalyAssessmentRecord.model_id == model_id,
            AnomalyAssessmentRecord.simulation_run_id == run_id,
        )
    ).all()
    return sum(1 for components in rows if PERTURBATION_HIDDEN_MARKER not in components)
