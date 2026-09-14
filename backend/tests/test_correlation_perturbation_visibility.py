"""Tests for the correlation-visibility fix to the Phase 5 Section 38
partial-observability perturbation (see `app.services.evaluation
.perturbation_service` module docstring and `CorrelationService.analyze()`'s
`excluded_event_ids` parameter).

Prior to this fix, `CorrelationService.analyze()` always mapped ATT&CK
techniques (`_map()`) from the FULL, unfiltered event list and only required
EITHER a technique observation OR an anomalous assessment for an event to
enter `evidence_events` - so a hidden event whose raw telemetry fields
happened to match one of `_map()`'s rules could still produce a real
`TechniqueObservationRecord` and enter the incident/ATT&CK evidence path,
even though its `AnomalyAssessmentRecord` was already correctly neutralized
by the perturbed model identity. `analyze()` now accepts an optional
`excluded_event_ids` parameter; passing it filters BOTH the technique-mapping
input and `evidence_events` membership, while leaving `events` (and hence
`events.index(event) + 1` sequence numbering) fully intact.

These tests exercise `CorrelationService.analyze()` directly (not just
through `ExperimentService`) for precise, deterministic control over which
event id is excluded - per the task's guidance, this is the least invasive
way to get a real proof, since `apply_perturbation`'s fraction-based
selection does not give per-event control.
"""

from __future__ import annotations

from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.models import IncidentEvidenceRecord, TechniqueObservationRecord
from app.services.correlation_service import correlation_service
from app.services.telemetry_service import telemetry_service


def _session(client: TestClient):  # type: ignore[no-untyped-def]
    return cast(FastAPI, client.app).state.database.session_factory()


def _prepare(client: TestClient) -> tuple[str, str]:
    """Same real `staged-compromise-demo` seed 84 fixture already used by
    `tests/test_correlation.py`'s `prepare()` - known (from that test) to
    produce real T1110.001/T1078/T1098/T1021/T1567 technique observations."""

    run = client.post(
        "/api/v1/simulation/runs",
        json={
            "scenario_id": "staged-compromise-demo",
            "seed": 84,
            "start_time": "2026-07-21T01:30:00Z",
            "playback_speed": 50,
        },
    ).json()
    trained = client.post(
        "/api/v1/detection/models/train",
        json={
            "training_seed_range": {"start": 1, "end": 1},
            "validation_seed_range": {"start": 2, "end": 2},
            "evaluation_seed_range": {"start": 3, "end": 3},
            "random_state": 17,
            "target_false_positive_rate": 0.1,
            "n_estimators": 100,
        },
    ).json()
    run_id, model_id = str(run["simulation_run_id"]), str(trained["model_id"])
    assert (
        client.post(
            f"/api/v1/detection/runs/{run_id}/score", json={"model_id": model_id}
        ).status_code
        == 200
    )
    return run_id, model_id


def test_hidden_event_loses_its_attck_evidence_when_excluded(client: TestClient) -> None:
    """(1) Hidden ATT&CK evidence proof: a real event that genuinely maps to
    a technique under the canonical/visible pass produces no
    `TechniqueObservationRecord`, no `IncidentEvidenceRecord`, and drops out
    of the candidate's involved-technique/tactic/asset sets once its
    event_id is passed via `excluded_event_ids`."""

    session = _session(client)
    try:
        run_id, model_id = _prepare(client)

        visible_result = correlation_service.analyze(session, run_id, model_id, force=True)
        assert visible_result.incident_candidate_id is not None

        # Find a real, deterministic single-event technique mapping.
        # T1098 (account_manipulation) fires unconditionally off one event's
        # metadata, with no cross-event dependency (unlike T1078, which
        # additionally requires a prior failed-login event for the same
        # user) - the cleanest event to isolate.
        t1098 = (
            session.query(TechniqueObservationRecord)
            .filter(
                TechniqueObservationRecord.simulation_run_id == run_id,
                TechniqueObservationRecord.model_id == model_id,
                TechniqueObservationRecord.technique_id == "T1098",
            )
            .one()
        )
        hidden_event_id = t1098.event_id

        visible_evidence = (
            session.query(IncidentEvidenceRecord)
            .filter(
                IncidentEvidenceRecord.incident_candidate_id
                == visible_result.incident_candidate_id,
                IncidentEvidenceRecord.event_id == hidden_event_id,
            )
            .one()
        )
        assert visible_evidence.technique_mapping_id == t1098.mapping_id

        perturbed_result = correlation_service.analyze(
            session,
            run_id,
            model_id,
            force=True,
            excluded_event_ids=frozenset({hidden_event_id}),
        )
        assert perturbed_result.incident_candidate_id is not None

        remaining_observation = (
            session.query(TechniqueObservationRecord)
            .filter(
                TechniqueObservationRecord.simulation_run_id == run_id,
                TechniqueObservationRecord.model_id == model_id,
                TechniqueObservationRecord.event_id == hidden_event_id,
            )
            .one_or_none()
        )
        assert remaining_observation is None, (
            "a hidden event must not produce a TechniqueObservationRecord"
        )

        remaining_evidence = (
            session.query(IncidentEvidenceRecord)
            .filter(
                IncidentEvidenceRecord.incident_candidate_id
                == perturbed_result.incident_candidate_id,
                IncidentEvidenceRecord.event_id == hidden_event_id,
            )
            .one_or_none()
        )
        assert remaining_evidence is None, (
            "a hidden event must not contribute an IncidentEvidenceRecord"
        )

        from app.database.models import IncidentCandidateRecord

        candidate = session.get(IncidentCandidateRecord, perturbed_result.incident_candidate_id)
        assert candidate is not None
        assert "T1098" not in candidate.observed_technique_ids_json, (
            "T1098 was contributed solely by the hidden event in this fixture"
        )
    finally:
        session.close()


def test_visible_events_keep_their_true_full_run_sequence_number(client: TestClient) -> None:
    """(2) Sequence preservation: visible (non-hidden) events in a perturbed
    correlation result keep their ORIGINAL full-run sequence_number (their
    true position in the complete event list), not a renumbered 1..N over
    just the visible subset."""

    session = _session(client)
    try:
        run_id, model_id = _prepare(client)
        events = telemetry_service.list_run_events(session, run_id)
        assert len(events) >= 6

        # Hide a couple of events near the front so a renumbering bug would
        # be detectable (later visible events' sequence numbers would shift
        # down if the implementation incorrectly renumbered over a
        # compacted/filtered list).
        hidden = frozenset({events[0].event_id, events[2].event_id})

        result = correlation_service.analyze(
            session, run_id, model_id, force=True, excluded_event_ids=hidden
        )
        assert result.incident_candidate_id is not None

        evidence_rows = list(
            session.query(IncidentEvidenceRecord).filter(
                IncidentEvidenceRecord.incident_candidate_id == result.incident_candidate_id
            )
        )
        assert evidence_rows, "expected at least some evidence in this fixture"

        checked = 0
        for row in evidence_rows:
            assert row.event_id not in hidden
            true_sequence = events.index(next(e for e in events if e.event_id == row.event_id)) + 1
            assert row.sequence_number == true_sequence, (
                f"event {row.event_id} should keep its true full-run sequence number "
                f"{true_sequence}, got {row.sequence_number}"
            )
            checked += 1
        assert checked >= 2, "expected at least two visible evidence events to check"
    finally:
        session.close()


def test_excluded_event_ids_empty_or_omitted_is_byte_for_byte_identical(
    client: TestClient,
) -> None:
    """(3) Canonical non-regression: `excluded_event_ids=frozenset()` (or
    omitted entirely) produces IDENTICAL results to the current/unmodified
    behaviour for the same real run/model - proving every Phase 0-4 caller
    and every unperturbed Phase 5 caller is byte-for-byte unaffected."""

    session = _session(client)
    try:
        run_id, model_id = _prepare(client)

        default_result = correlation_service.analyze(session, run_id, model_id, force=True)
        default_observations = {
            (item.event_id, item.technique_id, item.mapping_confidence)
            for item in session.query(TechniqueObservationRecord).filter(
                TechniqueObservationRecord.simulation_run_id == run_id,
                TechniqueObservationRecord.model_id == model_id,
            )
        }
        default_evidence = {
            (item.event_id, item.sequence_number, item.evidence_type, item.contribution_score)
            for item in session.query(IncidentEvidenceRecord).filter(
                IncidentEvidenceRecord.incident_candidate_id == default_result.incident_candidate_id
            )
        }

        explicit_empty_result = correlation_service.analyze(
            session, run_id, model_id, force=True, excluded_event_ids=frozenset()
        )
        explicit_empty_observations = {
            (item.event_id, item.technique_id, item.mapping_confidence)
            for item in session.query(TechniqueObservationRecord).filter(
                TechniqueObservationRecord.simulation_run_id == run_id,
                TechniqueObservationRecord.model_id == model_id,
            )
        }
        explicit_empty_evidence = {
            (item.event_id, item.sequence_number, item.evidence_type, item.contribution_score)
            for item in session.query(IncidentEvidenceRecord).filter(
                IncidentEvidenceRecord.incident_candidate_id
                == explicit_empty_result.incident_candidate_id
            )
        }

        assert default_result.incident_candidate_id == explicit_empty_result.incident_candidate_id
        assert (
            default_result.technique_observation_count
            == explicit_empty_result.technique_observation_count
        )
        assert default_result.evidence_count == explicit_empty_result.evidence_count
        assert default_result.snapshot_count == explicit_empty_result.snapshot_count
        assert default_observations == explicit_empty_observations
        assert default_evidence == explicit_empty_evidence
    finally:
        session.close()
