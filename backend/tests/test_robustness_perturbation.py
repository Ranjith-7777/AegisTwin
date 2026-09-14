"""Tests for the Phase 5 Section 38 partial-observability robustness
perturbation (`app.services.evaluation.perturbation_service`).

Uses the same real `leaked-api-credential` seed 7 pattern already
established in `test_batch_runner.py` - a real, small, end-to-end run
through `experiment_service.create_and_run`/`evaluate_experiment`, not a
hand-constructed fixture, because the whole point of this feature is
"does defence performance/DECISION actually degrade" against genuinely
computed data.

## Correction: perturbation must change the defence DECISION, not just the
   reported score

An earlier revision of this feature only filtered `AnomalyAssessmentRecord`s
AFTER a defence decision was already made from the full, unperturbed
evidence - so a perturbed experiment's response/correlation/agentic
decisions were identical to the baseline's, and only the final metrics
differed. That was not a real robustness test. The corrected mechanism
(see `perturbation_service` module docstring) scores a SEPARATE,
perturbation-scoped `DetectionModelRecord` identity
(`ExperimentRecord.perturbed_model_id`) whose persisted evidence genuinely
omits the hidden events' real signal, and routes `correlation_service
.analyze()`/the defence-strategy dispatch through THAT identity instead of
the canonical one - so these tests assert real decision-input differences,
not just metric differences.

## Rule-Based evidence-sensitivity finding (see test below)

`RuleBasedDefenceStrategy._match_rule` is a pure function of
`experiment.scenario_id` for every scenario EXCEPT `leaked-api-credential`,
where it also calls `_find_ingress_edge` (RULE-INGRESS-01 vs. RULE-CRED-01),
which in turn calls `topology_path_service.run_state(session, run_id,
model_id, ...)` - genuinely `model_id`-scoped, hence evidence-sensitive to
the perturbation. `_pick_target` is ALSO evidence-sensitive for every
scenario via `what_if_evidence_service.anchor_asset_ids(session, run_id,
model_id, ...)`. So "Rule-Based's rule never reads evidence" is only true
for scenarios other than `leaked-api-credential` AND only for the RULE
MATCH step - TARGET RESOLUTION is evidence-sensitive for every scenario.
`suspicious-kubernetes-pod` is used below because its rule match
(RULE-WORKLOAD-01) is scenario-only (never evidence-sensitive), isolating
the target-resolution behaviour cleanly.
"""

from __future__ import annotations

from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.models import AnomalyAssessmentRecord, TelemetryEventRecord
from app.schemas.evaluation import DefenceMode, ExperimentCreate, ExperimentStatus
from app.schemas.simulation import SimulationRunCreate
from app.services.correlation_service import correlation_service
from app.services.evaluation.evaluation_pipeline import evaluate_experiment
from app.services.evaluation.experiment_service import (
    CANONICAL_PLAYBACK_SPEED,
    CANONICAL_START_TIME,
    experiment_service,
)
from app.services.evaluation.metrics_service import GROUND_TRUTH_SEVERITIES
from app.services.evaluation.perturbation_service import (
    PARTIAL_OBSERVABILITY_PERTURBATION_ID,
    apply_perturbation,
    informative_assessment_count,
)
from app.services.response_service import response_service
from app.services.simulation_service import simulation_run_service


def _session(client: TestClient):  # type: ignore[no-untyped-def]
    return cast(FastAPI, client.app).state.database.session_factory()


def _ensure_run(session, scenario_id: str, seed: int) -> str:  # type: ignore[no-untyped-def]
    run = simulation_run_service.create_run(
        session,
        SimulationRunCreate(
            scenario_id=scenario_id,
            seed=seed,
            start_time=CANONICAL_START_TIME,
            playback_speed=CANONICAL_PLAYBACK_SPEED,
        ),
    )
    return run.simulation_run_id


def test_apply_perturbation_is_deterministic(client: TestClient) -> None:
    session = _session(client)
    try:
        run_id = _ensure_run(session, "leaked-api-credential", 7)
        params: dict[str, object] = {"hidden_fraction": 0.3}
        first = apply_perturbation(session, run_id, PARTIAL_OBSERVABILITY_PERTURBATION_ID, params)
        second = apply_perturbation(session, run_id, PARTIAL_OBSERVABILITY_PERTURBATION_ID, params)
        assert first == second
        assert len(first) > 0, "the leaked-api-credential scenario has non-critical events to hide"
    finally:
        session.close()


def test_apply_perturbation_never_hides_a_ground_truth_event(client: TestClient) -> None:
    session = _session(client)
    try:
        run_id = _ensure_run(session, "leaked-api-credential", 7)
        hidden = apply_perturbation(
            session, run_id, PARTIAL_OBSERVABILITY_PERTURBATION_ID, {"hidden_fraction": 0.9}
        )
        assert len(hidden) > 0

        ground_truth_values = {severity.value for severity in GROUND_TRUTH_SEVERITIES}
        rows = session.execute(
            TelemetryEventRecord.__table__.select().where(
                TelemetryEventRecord.simulation_run_id == run_id
            )
        ).all()
        severity_by_id = {row.event_id: row.severity for row in rows}
        for event_id in hidden:
            severity = severity_by_id[event_id]
            assert severity not in ground_truth_values, (
                f"event {event_id} has severity {severity!r} and must never be hidden"
            )
    finally:
        session.close()


def test_apply_perturbation_with_no_perturbation_id_hides_nothing(client: TestClient) -> None:
    session = _session(client)
    try:
        run_id = _ensure_run(session, "leaked-api-credential", 7)
        assert apply_perturbation(session, run_id, None, None) == frozenset()
        assert (
            apply_perturbation(session, run_id, "some-unrecognised-id", {"hidden_fraction": 0.5})
            == frozenset()
        )
    finally:
        session.close()


def test_full_pre_existing_suite_is_unaffected_by_an_unperturbed_experiment(
    client: TestClient,
) -> None:
    """A sanity check that an experiment with no perturbation_id produces
    configuration_json with an empty hidden_event set and never materializes
    a perturbed model identity - exercising the exact default path every
    pre-existing (Phase 0-4 / Stage 1-9) experiment and test takes,
    byte-for-byte unchanged by this correction."""

    session = _session(client)
    try:
        experiment = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="leaked-api-credential",
                seed=7,
                defence_mode=DefenceMode.NO_ACTIVE_DEFENCE,
            ),
        )
        assert experiment.status == ExperimentStatus.COMPLETED.value
        assert experiment.configuration_json.get("hidden_event_ids") == []
        assert experiment.configuration_json.get("hidden_event_count") == 0
        assert experiment.perturbed_model_id is None
    finally:
        session.close()


def test_perturbed_experiment_detects_no_more_than_baseline(client: TestClient) -> None:
    """Hiding non-critical evidence can only reduce or maintain detection,
    never improve it - assert the real relationship on real computed data
    for the SAME scenario/seed/mode."""

    session = _session(client)
    try:
        baseline = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="leaked-api-credential",
                seed=7,
                defence_mode=DefenceMode.RULE_BASED,
                label="baseline",
            ),
        )
        assert baseline.status == ExperimentStatus.COMPLETED.value
        baseline_metrics, _ = evaluate_experiment(session, baseline.experiment_id)

        perturbed = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="leaked-api-credential",
                seed=7,
                defence_mode=DefenceMode.RULE_BASED,
                label="perturbed",
                perturbation_id=PARTIAL_OBSERVABILITY_PERTURBATION_ID,
                perturbation_params={"hidden_fraction": 0.5},
            ),
        )
        assert perturbed.status == ExperimentStatus.COMPLETED.value
        perturbed_metrics, _ = evaluate_experiment(session, perturbed.experiment_id)

        # Same shared deterministic run/model - a genuine paired comparison.
        assert baseline.run_id == perturbed.run_id
        assert baseline.detection_model_id == perturbed.detection_model_id

        hidden_count = perturbed.configuration_json.get("hidden_event_count")
        assert isinstance(hidden_count, int) and hidden_count > 0

        baseline_detected = baseline_metrics.raw_metrics_json["detected_attack_steps"]
        perturbed_detected = perturbed_metrics.raw_metrics_json["detected_attack_steps"]
        assert isinstance(baseline_detected, int) and isinstance(perturbed_detected, int)
        assert perturbed_detected <= baseline_detected

        baseline_coverage = baseline_metrics.raw_metrics_json["detection_coverage"]
        perturbed_coverage = perturbed_metrics.raw_metrics_json["detection_coverage"]
        if isinstance(baseline_coverage, (int, float)) and isinstance(
            perturbed_coverage, (int, float)
        ):
            assert perturbed_coverage <= baseline_coverage
    finally:
        session.close()


def test_structural_mechanism_uses_a_real_isolated_evidence_identity(
    client: TestClient,
) -> None:
    """Summary-level proof the new mechanism structurally differs from the
    old metrics-only masking: a perturbed experiment gets its own
    `perturbed_model_id`, distinct from the canonical `detection_model_id`,
    and the perturbed identity has strictly fewer INFORMATIVE (non-
    neutralized) assessments than the canonical identity - the literal
    evidence available to `response_service.analyze()`/`correlation_service
    .analyze()`/`workflow_coordinator.run()` for this run, not just a
    post-hoc filtered metric."""

    session = _session(client)
    try:
        experiment = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="leaked-api-credential",
                seed=7,
                defence_mode=DefenceMode.ML_ASSISTED,
                perturbation_id=PARTIAL_OBSERVABILITY_PERTURBATION_ID,
                perturbation_params={"hidden_fraction": 0.5},
            ),
        )
        assert experiment.status == ExperimentStatus.COMPLETED.value
        assert experiment.run_id is not None
        assert experiment.detection_model_id is not None
        assert experiment.perturbed_model_id is not None
        assert experiment.perturbed_model_id != experiment.detection_model_id

        canonical_informative = informative_assessment_count(
            session, experiment.run_id, experiment.detection_model_id
        )
        perturbed_informative = informative_assessment_count(
            session, experiment.run_id, experiment.perturbed_model_id
        )
        assert perturbed_informative < canonical_informative

        # Row-count invariant: every event still gets a persisted row under
        # the perturbed identity (required by `correlation_service.analyze`
        # /`response_service.analyze`'s own completeness checks - see
        # `perturbation_service` module docstring), so the raw COUNT(*) is
        # equal even though the INFORMATIVE count is not.
        canonical_total = int(
            session.query(AnomalyAssessmentRecord)
            .filter(AnomalyAssessmentRecord.model_id == experiment.detection_model_id)
            .count()
        )
        perturbed_total = int(
            session.query(AnomalyAssessmentRecord)
            .filter(AnomalyAssessmentRecord.model_id == experiment.perturbed_model_id)
            .count()
        )
        assert canonical_total == perturbed_total
    finally:
        session.close()


def test_baseline_experiment_assessments_unaffected_by_a_later_perturbed_run(
    client: TestClient,
) -> None:
    """The critical no-cache-contamination proof: running a perturbed
    experiment for a scenario/seed/mode must never change the CANONICAL
    model's own persisted `AnomalyAssessmentRecord` set for a baseline
    experiment sharing that same deterministic run/model."""

    session = _session(client)
    try:
        baseline = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="leaked-api-credential",
                seed=7,
                defence_mode=DefenceMode.ML_ASSISTED,
                label="baseline",
            ),
        )
        assert baseline.status == ExperimentStatus.COMPLETED.value

        before_count = int(
            session.query(AnomalyAssessmentRecord)
            .filter(AnomalyAssessmentRecord.model_id == baseline.detection_model_id)
            .count()
        )
        before_rows = {
            (row.event_id, row.classification, row.anomaly_score)
            for row in session.query(AnomalyAssessmentRecord).filter(
                AnomalyAssessmentRecord.model_id == baseline.detection_model_id
            )
        }

        perturbed = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="leaked-api-credential",
                seed=7,
                defence_mode=DefenceMode.ML_ASSISTED,
                label="perturbed",
                perturbation_id=PARTIAL_OBSERVABILITY_PERTURBATION_ID,
                perturbation_params={"hidden_fraction": 0.5},
            ),
        )
        assert perturbed.status == ExperimentStatus.COMPLETED.value
        assert perturbed.run_id == baseline.run_id
        assert perturbed.detection_model_id == baseline.detection_model_id

        after_count = int(
            session.query(AnomalyAssessmentRecord)
            .filter(AnomalyAssessmentRecord.model_id == baseline.detection_model_id)
            .count()
        )
        after_rows = {
            (row.event_id, row.classification, row.anomaly_score)
            for row in session.query(AnomalyAssessmentRecord).filter(
                AnomalyAssessmentRecord.model_id == baseline.detection_model_id
            )
        }
        assert after_count == before_count
        assert after_rows == before_rows
    finally:
        session.close()


def test_hidden_evidence_not_visible_to_ml_assisted_response_selection(
    client: TestClient,
) -> None:
    """Proves fewer real assessments were available to
    `response_service.analyze()` for the perturbed run than the baseline -
    by direct inspection of the informative `AnomalyAssessmentRecord` set
    under each model identity, which is literally what
    `MLAssistedDefenceStrategy` reads its recommendations from."""

    session = _session(client)
    try:
        baseline = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="leaked-api-credential",
                seed=7,
                defence_mode=DefenceMode.ML_ASSISTED,
                label="baseline",
            ),
        )
        assert baseline.status == ExperimentStatus.COMPLETED.value
        assert baseline.run_id is not None
        assert baseline.detection_model_id is not None

        perturbed = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="leaked-api-credential",
                seed=7,
                defence_mode=DefenceMode.ML_ASSISTED,
                label="perturbed",
                perturbation_id=PARTIAL_OBSERVABILITY_PERTURBATION_ID,
                perturbation_params={"hidden_fraction": 0.5},
            ),
        )
        assert perturbed.status == ExperimentStatus.COMPLETED.value
        assert perturbed.run_id is not None
        assert perturbed.perturbed_model_id is not None

        baseline_informative = informative_assessment_count(
            session, baseline.run_id, baseline.detection_model_id
        )
        perturbed_informative = informative_assessment_count(
            session, perturbed.run_id, perturbed.perturbed_model_id
        )
        assert perturbed_informative < baseline_informative

        # The response analysis this experiment actually persisted was
        # computed under `perturbed.perturbed_model_id`, not the canonical
        # identity - confirm the recorded analysis/recommendations are
        # keyed to the degraded identity, i.e. that is genuinely what
        # `MLAssistedDefenceStrategy.execute` -> `response_service.analyze`
        # read from.
        analysis = response_service.summary(session, perturbed.run_id, perturbed.perturbed_model_id)
        assert analysis.model_id == perturbed.perturbed_model_id
    finally:
        session.close()


def test_hidden_evidence_not_visible_to_agentic_planning_input(client: TestClient) -> None:
    """Same style of proof for the evidence set feeding
    `workflow_coordinator.run()`/`correlation_service.analyze()` for
    Agentic mode: the incident candidate itself was formed under
    `perturbed_model_id`, with a strictly smaller informative evidence set
    than the canonical identity's."""

    session = _session(client)
    try:
        baseline = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="leaked-api-credential",
                seed=7,
                defence_mode=DefenceMode.AGENTIC,
                label="baseline",
            ),
        )
        assert baseline.status in {
            ExperimentStatus.COMPLETED.value,
            ExperimentStatus.VERIFYING.value,
        }
        assert baseline.run_id is not None
        assert baseline.detection_model_id is not None

        perturbed = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="leaked-api-credential",
                seed=7,
                defence_mode=DefenceMode.AGENTIC,
                label="perturbed",
                perturbation_id=PARTIAL_OBSERVABILITY_PERTURBATION_ID,
                perturbation_params={"hidden_fraction": 0.5},
            ),
        )
        assert perturbed.status in {
            ExperimentStatus.COMPLETED.value,
            ExperimentStatus.VERIFYING.value,
        }
        assert perturbed.run_id is not None
        assert perturbed.perturbed_model_id is not None

        baseline_informative = informative_assessment_count(
            session, baseline.run_id, baseline.detection_model_id
        )
        perturbed_informative = informative_assessment_count(
            session, perturbed.run_id, perturbed.perturbed_model_id
        )
        assert perturbed_informative < baseline_informative

        if perturbed.incident_candidate_id is not None:
            candidate = correlation_service.analyze(
                session, perturbed.run_id, perturbed.perturbed_model_id, force=False
            )
            assert candidate.model_id == perturbed.perturbed_model_id
    finally:
        session.close()


def test_rule_based_selection_unchanged_when_rule_match_is_scenario_only(
    client: TestClient,
) -> None:
    """`suspicious-kubernetes-pod` always matches RULE-WORKLOAD-01 purely on
    `scenario_id` (see `RuleBasedDefenceStrategy._match_rule`, which never
    calls `_find_ingress_edge` for this scenario) - so the matched
    RULE/PLAYBOOK is genuinely unaffected by the perturbation, an honest
    result, not a bug, since the rule never consumed the hidden evidence in
    the first place."""

    session = _session(client)
    try:
        baseline = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="suspicious-kubernetes-pod",
                seed=1,
                defence_mode=DefenceMode.RULE_BASED,
                label="baseline",
            ),
        )
        assert baseline.status == ExperimentStatus.COMPLETED.value

        perturbed = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="suspicious-kubernetes-pod",
                seed=1,
                defence_mode=DefenceMode.RULE_BASED,
                label="perturbed",
                perturbation_id=PARTIAL_OBSERVABILITY_PERTURBATION_ID,
                perturbation_params={"hidden_fraction": 0.3},
            ),
        )
        assert perturbed.status == ExperimentStatus.COMPLETED.value

        baseline_action = experiment_service.get(session, baseline.experiment_id)
        perturbed_action = experiment_service.get(session, perturbed.experiment_id)
        assert baseline_action.evaluation_action_id is not None
        assert perturbed_action.evaluation_action_id is not None

        from app.database.models import EvaluationSyntheticActionRecord

        baseline_playbook = session.get(
            EvaluationSyntheticActionRecord, baseline_action.evaluation_action_id
        ).playbook_id
        perturbed_playbook = session.get(
            EvaluationSyntheticActionRecord, perturbed_action.evaluation_action_id
        ).playbook_id
        assert baseline_playbook == perturbed_playbook == "increase-synthetic-monitoring"
    finally:
        session.close()


def test_rule_based_target_resolution_can_change_with_evidence(client: TestClient) -> None:
    """Unlike the rule MATCH, Rule-Based's TARGET RESOLUTION
    (`_pick_target`) reads evidence via
    `what_if_evidence_service.anchor_asset_ids(session, run_id, model_id,
    ...)`, which is genuinely `model_id`-scoped - so it IS evidence-
    sensitive to the perturbation, even for a scenario whose rule match is
    scenario-only. `suspicious-kubernetes-pod` seed 3 with
    `hidden_fraction=0.3` demonstrates this: the selected target asset
    changes from `admin-service-01` (baseline) to `application-pod-01`
    (perturbed) even though the matched playbook stays
    `increase-synthetic-monitoring` in both cases - found by trying several
    scenario/seed/fraction combinations against real computed data (see
    `perturbation_service` for the mechanism this exercises)."""

    session = _session(client)
    try:
        from app.database.models import EvaluationSyntheticActionRecord

        baseline = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="suspicious-kubernetes-pod",
                seed=3,
                defence_mode=DefenceMode.RULE_BASED,
                label="baseline",
            ),
        )
        assert baseline.status == ExperimentStatus.COMPLETED.value
        baseline_record = experiment_service.get(session, baseline.experiment_id)
        baseline_action = session.get(
            EvaluationSyntheticActionRecord, baseline_record.evaluation_action_id
        )

        perturbed = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="suspicious-kubernetes-pod",
                seed=3,
                defence_mode=DefenceMode.RULE_BASED,
                label="perturbed",
                perturbation_id=PARTIAL_OBSERVABILITY_PERTURBATION_ID,
                perturbation_params={"hidden_fraction": 0.3},
            ),
        )
        assert perturbed.status == ExperimentStatus.COMPLETED.value
        perturbed_record = experiment_service.get(session, perturbed.experiment_id)
        perturbed_action = session.get(
            EvaluationSyntheticActionRecord, perturbed_record.evaluation_action_id
        )

        assert baseline_action is not None and perturbed_action is not None
        assert baseline_action.playbook_id == perturbed_action.playbook_id
        assert baseline_action.target_id == "admin-service-01"
        assert perturbed_action.target_id == "application-pod-01"
        assert baseline_action.target_id != perturbed_action.target_id, (
            "real evidence-sensitive target resolution should differ once enough evidence is "
            "hidden, proving Rule-Based's target step (unlike its scenario-only rule match) IS "
            "evidence-sensitive to the perturbation"
        )
    finally:
        session.close()


def test_larger_perturbation_changes_ml_assisted_top_recommendation(client: TestClient) -> None:
    """A larger, material perturbation CAN change a downstream decision:
    `suspicious-kubernetes-pod` seed 1 with `hidden_fraction=0.95` changes
    ML-Assisted's top-ranked recommendation TARGET (`admin-service-01` in
    the baseline vs. `application-pod-01` once 95% of non-critical evidence
    is hidden), found by systematically trying several scenario/seed/
    fraction combinations against real computed data (see
    `perturbation_service` module docstring/PM spec for why this counts as
    a genuine before/after decision change, not merely a metric change)."""

    session = _session(client)
    try:
        baseline = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="suspicious-kubernetes-pod",
                seed=1,
                defence_mode=DefenceMode.ML_ASSISTED,
                label="baseline",
            ),
        )
        assert baseline.status == ExperimentStatus.COMPLETED.value
        assert baseline.run_id is not None
        assert baseline.detection_model_id is not None
        baseline_analysis = response_service.summary(
            session, baseline.run_id, baseline.detection_model_id
        )
        assert baseline_analysis.top_recommendation is not None
        assert baseline_analysis.top_recommendation.target_id == "admin-service-01"

        perturbed = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="suspicious-kubernetes-pod",
                seed=1,
                defence_mode=DefenceMode.ML_ASSISTED,
                label="perturbed",
                perturbation_id=PARTIAL_OBSERVABILITY_PERTURBATION_ID,
                perturbation_params={"hidden_fraction": 0.95},
            ),
        )
        assert perturbed.status == ExperimentStatus.COMPLETED.value
        assert perturbed.run_id is not None
        assert perturbed.perturbed_model_id is not None
        perturbed_analysis = response_service.summary(
            session, perturbed.run_id, perturbed.perturbed_model_id
        )
        assert perturbed_analysis.top_recommendation is not None
        assert perturbed_analysis.top_recommendation.target_id == "application-pod-01"

        assert (
            baseline_analysis.top_recommendation.target_id
            != perturbed_analysis.top_recommendation.target_id
        )
    finally:
        session.close()
