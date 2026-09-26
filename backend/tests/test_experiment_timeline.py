"""Integration tests for the Phase 5 Stage 5 Experiment Timeline
(`app.services.evaluation.timeline_service`) and the additive Phase 5
domain events (`app.events.types.EventType.EVALUATION_*`).

Runs REAL experiments end-to-end through `experiment_service.create_and_run`
+ `evaluate_experiment` (never hand-constructed fixtures) so the timeline
reconstruction is exercised against genuine Phase 1-4 rows, matching the
style of `test_batch_runner.py`.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models import ExperimentRecord
from app.events.bus import InProcessEventBus
from app.events.envelope import DomainEvent
from app.events.registry import use_event_bus
from app.events.types import EventType
from app.schemas.evaluation import DefenceMode, ExperimentCreate, TimelineEvent
from app.services.evaluation.evaluation_pipeline import evaluate_experiment
from app.services.evaluation.experiment_service import experiment_service
from app.services.evaluation.timeline_service import STAGE_ORDER, experiment_timeline_service


def _session(client: TestClient) -> Session:
    return cast(Session, cast(FastAPI, client.app).state.database.session_factory())


def _run(
    session: Session, scenario_id: str, seed: int, defence_mode: DefenceMode
) -> ExperimentRecord:
    request = ExperimentCreate(scenario_id=scenario_id, seed=seed, defence_mode=defence_mode)
    experiment = experiment_service.create_and_run(session, request)
    assert experiment.status == "completed", experiment.failure_message
    evaluate_experiment(session, experiment.experiment_id)
    return experiment


def _by_stage(events: list[TimelineEvent]) -> dict[str, TimelineEvent]:
    return {event.stage: event for event in events}


@pytest.fixture
def isolated_bus() -> Iterator[InProcessEventBus]:
    bus = InProcessEventBus()
    with use_event_bus(bus):
        yield bus


def test_agentic_experiment_timeline_full_stage_order(
    client: TestClient, isolated_bus: InProcessEventBus
) -> None:
    session = _session(client)
    try:
        experiment = _run(session, "leaked-api-credential", 7, DefenceMode.AGENTIC)

        timeline = experiment_timeline_service.build_timeline(session, experiment.experiment_id)
        assert [event.stage for event in timeline.events] == list(STAGE_ORDER)
        assert [event.sequence for event in timeline.events] == list(range(1, len(STAGE_ORDER) + 1))

        by_stage = _by_stage(timeline.events)

        always_occurred = [
            "experiment_created",
            "red_scenario_started",
            "telemetry_generated",
            "detection",
            "incident_correlated",
            "response_selected",
            "synthetic_execution",
            "verification",
            "experiment_completed",
        ]
        for stage in always_occurred:
            event = by_stage[stage]
            assert event.status == "occurred", f"{stage}: {event.summary}"
            assert event.resource_ids, f"{stage} should carry resource ids"
            assert event.summary

        # Attack Graph / Blast Radius are never persisted per-call - always
        # honestly marked N/A, for every experiment/mode.
        assert by_stage["attack_graph_evaluated"].status == "skipped_not_applicable"
        assert by_stage["blast_radius_evaluated"].status == "skipped_not_applicable"

        # Agentic-only stages: real what-if/policy evidence must exist.
        assert by_stage["what_if_planning"].status == "occurred"
        assert by_stage["policy_evaluated"].status == "occurred"

        # This scenario/seed's smoke history (per the Stage brief) verifies
        # successfully, so no rollback should have been needed - but assert
        # against reality rather than forcing the outcome.
        verification_event = by_stage["verification"]
        rollback_event = by_stage["rollback"]
        if "successful" in verification_event.summary:
            assert rollback_event.status == "skipped_not_applicable"
        else:
            assert rollback_event.status in ("occurred", "failed")

        # Every stage carries the same correlation_id (the experiment_id).
        for event in timeline.events:
            assert event.correlation_id == experiment.experiment_id
    finally:
        session.close()


def test_rule_based_skips_what_if_and_policy_by_design(client: TestClient) -> None:
    session = _session(client)
    try:
        experiment = _run(session, "leaked-api-credential", 7, DefenceMode.RULE_BASED)
        timeline = experiment_timeline_service.build_timeline(session, experiment.experiment_id)
        by_stage = _by_stage(timeline.events)

        for stage in ("what_if_planning", "policy_evaluated"):
            event = by_stage[stage]
            assert event.status == "skipped_not_applicable"
            assert "by design" in event.summary
            assert "rule_based" in event.summary

        # rule_based still selects and executes a real response.
        assert by_stage["response_selected"].status == "occurred"
    finally:
        session.close()


def test_no_active_defence_is_a_fair_baseline(client: TestClient) -> None:
    session = _session(client)
    try:
        experiment = _run(session, "leaked-api-credential", 7, DefenceMode.NO_ACTIVE_DEFENCE)
        timeline = experiment_timeline_service.build_timeline(session, experiment.experiment_id)
        by_stage = _by_stage(timeline.events)

        # Fairness property: it still SAW the incident...
        assert by_stage["detection"].status == "occurred"
        assert by_stage["incident_correlated"].status == "occurred"

        # ...but never acted on it.
        for stage in (
            "response_selected",
            "what_if_planning",
            "policy_evaluated",
            "approval",
            "synthetic_execution",
            "verification",
            "rollback",
        ):
            event = by_stage[stage]
            assert event.status == "skipped_not_applicable", f"{stage}: {event.summary}"

        assert by_stage["experiment_completed"].status == "occurred"
    finally:
        session.close()


def test_phase5_events_share_one_correlation_id_per_experiment(
    client: TestClient, isolated_bus: InProcessEventBus
) -> None:
    session = _session(client)
    seen: list[DomainEvent] = []  # type: ignore[type-arg]
    for event_type in (
        EventType.EVALUATION_EXPERIMENT_STARTED,
        EventType.EVALUATION_DEFENCE_COMPLETED,
        EventType.EVALUATION_EXPERIMENT_COMPLETED,
        EventType.EVALUATION_METRICS_COMPUTED,
    ):
        isolated_bus.subscribe(event_type, seen.append)
    try:
        experiment = _run(session, "leaked-api-credential", 7, DefenceMode.ML_ASSISTED)

        event_types_seen = {event.event_type for event in seen}
        assert event_types_seen == {
            EventType.EVALUATION_EXPERIMENT_STARTED,
            EventType.EVALUATION_DEFENCE_COMPLETED,
            EventType.EVALUATION_EXPERIMENT_COMPLETED,
            EventType.EVALUATION_METRICS_COMPUTED,
        }
        correlation_ids = {event.correlation_id for event in seen}
        assert correlation_ids == {experiment.experiment_id}
    finally:
        session.close()


def test_batch_created_event_correlates_by_batch_id(
    client: TestClient, isolated_bus: InProcessEventBus
) -> None:
    from app.services.evaluation.batch_service import BatchService

    session = _session(client)
    seen: list[DomainEvent] = []  # type: ignore[type-arg]
    isolated_bus.subscribe(EventType.EVALUATION_BATCH_CREATED, seen.append)
    isolated_bus.subscribe(EventType.EVALUATION_EXPERIMENT_STARTED, seen.append)
    try:
        batch = BatchService().create_batch(
            session,
            scenario_ids=["leaked-api-credential"],
            seeds=[7],
            defence_modes=[DefenceMode.NO_ACTIVE_DEFENCE],
        )
        batch_created = [e for e in seen if e.event_type == EventType.EVALUATION_BATCH_CREATED]
        started = [e for e in seen if e.event_type == EventType.EVALUATION_EXPERIMENT_STARTED]
        assert len(batch_created) == 1
        assert batch_created[0].correlation_id == batch.batch_id
        assert len(started) == 1
        assert started[0].causation_id == batch.batch_id
    finally:
        session.close()
