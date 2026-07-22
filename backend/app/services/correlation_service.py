from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import (
    AnomalyAssessmentRecord,
    DetectionModelRecord,
    IncidentCandidateRecord,
    IncidentCandidateSnapshotRecord,
    IncidentEvidenceRecord,
    SimulationRunRecord,
    TechniqueObservationRecord,
)
from app.schemas.correlation import (
    CorrelationAnalysisResult,
    IncidentCandidate,
)
from app.schemas.telemetry import TelemetryEvent
from app.services.mitre_catalogue_service import CATALOGUE, mitre_catalogue_service
from app.services.telemetry_service import telemetry_service

MAPPER_VERSION = "conservative-mapper-v1"
ENGINE_VERSION = "causal-correlation-v1"
NAMESPACE = UUID("fd7b09c8-4a58-49d2-96cf-89794aed75d9")
WEIGHTS = {
    "temporal_proximity": 0.15,
    "entity_continuity": 0.20,
    "anomaly_evidence": 0.20,
    "technique_diversity": 0.15,
    "tactic_progression": 0.15,
    "infrastructure_continuity": 0.15,
}


class CorrelationService:
    def analyze(
        self, session: Session, run_id: str, model_id: str, force: bool
    ) -> CorrelationAnalysisResult:
        if session.get(SimulationRunRecord, run_id) is None:
            raise ApplicationError(
                "SIMULATION_RUN_NOT_FOUND", "The simulation run was not found.", 404
            )
        model = session.get(DetectionModelRecord, model_id)
        if model is None or not model.synthetic:
            raise ApplicationError(
                "DETECTION_MODEL_NOT_FOUND", "A synthetic detection model is required.", 404
            )
        events = telemetry_service.list_run_events(session, run_id)
        assessments = list(
            session.scalars(
                select(AnomalyAssessmentRecord)
                .where(
                    AnomalyAssessmentRecord.simulation_run_id == run_id,
                    AnomalyAssessmentRecord.model_id == model_id,
                )
                .order_by(AnomalyAssessmentRecord.sequence_number)
            )
        )
        if len(assessments) != len(events):
            raise ApplicationError(
                "ASSESSMENTS_INCOMPLETE",
                "Complete persisted assessments are required before correlation.",
                409,
            )
        existing = session.scalar(
            select(IncidentCandidateRecord).where(
                IncidentCandidateRecord.simulation_run_id == run_id,
                IncidentCandidateRecord.model_id == model_id,
                IncidentCandidateRecord.correlation_engine_version == ENGINE_VERSION,
            )
        )
        if existing is not None and not force:
            return self._result(session, existing, False)
        if force:
            self._delete_existing(session, run_id, model_id)
        mitre_catalogue_service.ensure(session)
        observations = self._map(events, model_id)
        for item in observations:
            session.add(item)
        assessment_by_event = {item.event_id: item for item in assessments}
        observation_by_event = {item.event_id: item for item in observations}
        evidence_events = [
            event
            for event in events
            if event.event_id in observation_by_event
            or assessment_by_event[event.event_id].classification == "anomalous"
        ]
        if not evidence_events:
            return CorrelationAnalysisResult(
                simulation_run_id=run_id,
                model_id=model_id,
                incident_candidate_id=None,
                technique_observation_count=0,
                evidence_count=0,
                snapshot_count=0,
                correlation_engine_version=ENGINE_VERSION,
                force_reanalyze=force,
                synthetic=True,
            )
        candidate_id = str(uuid5(NAMESPACE, f"candidate:{run_id}:{model_id}:{ENGINE_VERSION}"))
        now = datetime.now(UTC)
        evidence_records: list[IncidentEvidenceRecord] = []
        for event in evidence_events:
            sequence = events.index(event) + 1
            assessment = assessment_by_event[event.event_id]
            observation = observation_by_event.get(event.event_id)
            evidence = IncidentEvidenceRecord(
                evidence_id=str(uuid5(NAMESPACE, f"evidence:{candidate_id}:{event.event_id}")),
                incident_candidate_id=candidate_id,
                event_id=event.event_id,
                assessment_id=assessment.assessment_id,
                technique_mapping_id=observation.mapping_id if observation else None,
                sequence_number=sequence,
                evidence_type="technique_and_anomaly"
                if observation and assessment.classification == "anomalous"
                else "technique_observation"
                if observation
                else "anomaly_assessment",
                contribution_score=max(
                    assessment.anomaly_score, observation.mapping_confidence if observation else 0.0
                ),
                rationale=observation.rationale
                if observation
                else "Persisted anomaly assessment deviates from the synthetic normal baseline.",
                synthetic=True,
            )
            session.add(evidence)
            evidence_records.append(evidence)
        components = self._components(evidence_events, assessments, observations)
        score = sum(WEIGHTS[name] * value for name, value in components.items())
        techniques = sorted({item.technique_id for item in observations})
        tactics = sorted({item.tactic for item in observations})
        state, priority = self._state(score, len(evidence_records), len(techniques), len(tactics))
        assets = sorted(
            {
                asset
                for event in evidence_events
                for asset in (event.source_id, event.destination_id)
                if asset
            }
        )
        candidate = IncidentCandidateRecord(
            incident_candidate_id=candidate_id,
            simulation_run_id=run_id,
            model_id=model_id,
            title="Related unusual synthetic activity",
            summary=(
                "Evidence-based correlation of related synthetic telemetry, assessments and "
                "local ATT&CK observations."
            ),
            correlation_state=state,
            priority=priority,
            correlation_score=score,
            component_scores_json=components,
            first_sequence_number=evidence_records[0].sequence_number,
            latest_sequence_number=evidence_records[-1].sequence_number,
            first_observed_at=evidence_events[0].timestamp,
            latest_observed_at=evidence_events[-1].timestamp,
            primary_user_id=next((item.user_id for item in evidence_events if item.user_id), None),
            primary_device_id=next(
                (item.device_id for item in evidence_events if item.device_id), None
            ),
            involved_asset_ids_json=assets,
            observed_tactic_ids_json=tactics,
            observed_technique_ids_json=techniques,
            evidence_count=len(evidence_records),
            correlation_engine_version=ENGINE_VERSION,
            synthetic=True,
            created_at=now,
            updated_at=now,
        )
        session.add(candidate)
        for sequence in sorted({item.sequence_number for item in evidence_records}):
            available_evidence = [
                item for item in evidence_records if item.sequence_number <= sequence
            ]
            available_observations = [
                item for item in observations if item.sequence_number <= sequence
            ]
            available_events = events[:sequence]
            causal_components = self._components(
                available_events, assessments[:sequence], available_observations
            )
            causal_score = sum(WEIGHTS[name] * value for name, value in causal_components.items())
            causal_techniques = sorted({item.technique_id for item in available_observations})
            causal_tactics = sorted({item.tactic for item in available_observations})
            causal_state, causal_priority = self._state(
                causal_score, len(available_evidence), len(causal_techniques), len(causal_tactics)
            )
            snapshot = {
                "incident_candidate_id": candidate_id,
                "simulation_run_id": run_id,
                "model_id": model_id,
                "title": candidate.title,
                "correlation_state": causal_state,
                "priority": causal_priority,
                "correlation_score": causal_score,
                "component_scores": causal_components,
                "first_sequence_number": available_evidence[0].sequence_number,
                "latest_sequence_number": sequence,
                "evidence_count": len(available_evidence),
                "involved_asset_ids": sorted(
                    {
                        asset
                        for event in available_events
                        for asset in (event.source_id, event.destination_id)
                        if asset
                    }
                ),
                "observed_tactic_ids": causal_tactics,
                "observed_technique_ids": causal_techniques,
                "primary_user_id": candidate.primary_user_id,
                "primary_device_id": candidate.primary_device_id,
                "synthetic": True,
            }
            session.add(
                IncidentCandidateSnapshotRecord(
                    snapshot_id=str(uuid5(NAMESPACE, f"snapshot:{candidate_id}:{sequence}")),
                    incident_candidate_id=candidate_id,
                    sequence_number=sequence,
                    snapshot_json=snapshot,
                    synthetic=True,
                )
            )
        session.flush()
        return self._result(session, candidate, force)

    def _map(self, events: list[TelemetryEvent], model_id: str) -> list[TechniqueObservationRecord]:
        results: list[TechniqueObservationRecord] = []
        failed_users: set[str] = set()
        catalogue = {item[0]: item for item in CATALOGUE}
        for sequence, event in enumerate(events, 1):
            metadata = event.metadata
            selected: tuple[str, float, str] | None = None
            if event.failed_attempts >= 5 or metadata.get("attempt_pattern") == "repeated":
                selected = (
                    "T1110.001",
                    0.90,
                    "At least five repeated synthetic authentication failures were observed.",
                )
                if event.user_id:
                    failed_users.add(event.user_id)
            elif (
                event.outcome.value == "success"
                and event.user_id in failed_users
                and event.event_type.value == "authentication"
            ):
                selected = (
                    "T1078",
                    0.72,
                    "A successful synthetic login followed repeated failures for the same user; "
                    "this is not proof of credential theft.",
                )
            elif metadata.get("account_manipulation") is True:
                selected = (
                    "T1098",
                    0.92,
                    "Telemetry explicitly records synthetic account permission manipulation.",
                )
            elif isinstance(metadata.get("remote_service"), str):
                selected = (
                    "T1021",
                    0.88,
                    "Telemetry explicitly identifies a synthetic remote service channel.",
                )
            elif metadata.get("channel_type") == "synthetic_c2":
                selected = (
                    "T1041",
                    0.90,
                    "Transfer explicitly uses an existing synthetic C2 channel.",
                )
            elif metadata.get("channel_type") == "synthetic_web_service" and isinstance(
                metadata.get("web_service"), str
            ):
                selected = (
                    "T1567",
                    0.90,
                    "Transfer explicitly uses an identified synthetic web service.",
                )
            if selected is None:
                continue
            technique_id, confidence, rationale = selected
            definition = catalogue[technique_id]
            results.append(
                TechniqueObservationRecord(
                    mapping_id=str(
                        uuid5(
                            NAMESPACE,
                            f"mapping:{model_id}:{event.event_id}:{technique_id}:{MAPPER_VERSION}",
                        )
                    ),
                    technique_id=technique_id,
                    technique_name=definition[1],
                    simulation_run_id=event.simulation_run_id,
                    model_id=model_id,
                    event_id=event.event_id,
                    sequence_number=sequence,
                    mapping_confidence=confidence,
                    evidence_fields_json={
                        "event_type": event.event_type.value,
                        "action": event.action.value,
                        "outcome": event.outcome.value,
                        "failed_attempts": event.failed_attempts,
                        "metadata": metadata,
                    },
                    rationale=rationale,
                    tactic=definition[2][0],
                    mapper_version=MAPPER_VERSION,
                    synthetic=True,
                )
            )
        return results

    @staticmethod
    def _components(
        events: list[TelemetryEvent],
        assessments: list[AnomalyAssessmentRecord],
        observations: list[TechniqueObservationRecord],
    ) -> dict[str, float]:
        if not events:
            return {name: 0.0 for name in WEIGHTS}
        span = max(0.0, (events[-1].timestamp - events[0].timestamp).total_seconds())
        users = [item.user_id for item in events if item.user_id]
        devices = [item.device_id for item in events if item.device_id]
        entity = max((users.count(item) for item in set(users)), default=0) / max(1, len(users))
        entity = max(
            entity,
            max((devices.count(item) for item in set(devices)), default=0) / max(1, len(devices)),
        )
        anomalous = [
            item.anomaly_score for item in assessments if item.classification == "anomalous"
        ]
        paths = [
            (events[index].destination_id, events[index + 1].source_id)
            for index in range(len(events) - 1)
        ]
        return {
            "temporal_proximity": max(0.0, 1 - span / 900),
            "entity_continuity": entity,
            "anomaly_evidence": min(1.0, sum(anomalous) / 3),
            "technique_diversity": min(1.0, len({item.technique_id for item in observations}) / 4),
            "tactic_progression": min(1.0, len({item.tactic for item in observations}) / 3),
            "infrastructure_continuity": sum(left == right for left, right in paths)
            / max(1, len(paths)),
        }

    @staticmethod
    def _state(score: float, evidence: int, techniques: int, tactics: int) -> tuple[str, str]:
        if score >= 0.65 and evidence >= 5 and techniques >= 4 and tactics >= 3:
            return "high_priority", "high"
        if score >= 0.42 and evidence >= 3 and techniques >= 2:
            return "correlated", "medium"
        return "monitoring", "low"

    @staticmethod
    def _delete_existing(session: Session, run_id: str, model_id: str) -> None:
        candidates = list(
            session.scalars(
                select(IncidentCandidateRecord.incident_candidate_id).where(
                    IncidentCandidateRecord.simulation_run_id == run_id,
                    IncidentCandidateRecord.model_id == model_id,
                )
            )
        )
        if candidates:
            session.execute(
                delete(IncidentCandidateSnapshotRecord).where(
                    IncidentCandidateSnapshotRecord.incident_candidate_id.in_(candidates)
                )
            )
            session.execute(
                delete(IncidentEvidenceRecord).where(
                    IncidentEvidenceRecord.incident_candidate_id.in_(candidates)
                )
            )
            session.execute(
                delete(IncidentCandidateRecord).where(
                    IncidentCandidateRecord.incident_candidate_id.in_(candidates)
                )
            )
        session.execute(
            delete(TechniqueObservationRecord).where(
                TechniqueObservationRecord.simulation_run_id == run_id,
                TechniqueObservationRecord.model_id == model_id,
            )
        )

    def _result(
        self, session: Session, candidate: IncidentCandidateRecord, force: bool
    ) -> CorrelationAnalysisResult:
        observations = int(
            session.scalar(
                select(func.count())
                .select_from(TechniqueObservationRecord)
                .where(
                    TechniqueObservationRecord.simulation_run_id == candidate.simulation_run_id,
                    TechniqueObservationRecord.model_id == candidate.model_id,
                )
            )
            or 0
        )
        snapshots = int(
            session.scalar(
                select(func.count())
                .select_from(IncidentCandidateSnapshotRecord)
                .where(
                    IncidentCandidateSnapshotRecord.incident_candidate_id
                    == candidate.incident_candidate_id
                )
            )
            or 0
        )
        return CorrelationAnalysisResult(
            simulation_run_id=candidate.simulation_run_id,
            model_id=candidate.model_id,
            incident_candidate_id=candidate.incident_candidate_id,
            technique_observation_count=observations,
            evidence_count=candidate.evidence_count,
            snapshot_count=snapshots,
            correlation_engine_version=ENGINE_VERSION,
            force_reanalyze=force,
            synthetic=True,
        )

    def candidate_schema(self, record: IncidentCandidateRecord) -> IncidentCandidate:
        return IncidentCandidate(
            incident_candidate_id=record.incident_candidate_id,
            simulation_run_id=record.simulation_run_id,
            model_id=record.model_id,
            title=record.title,
            summary=record.summary,
            correlation_state=record.correlation_state,
            priority=record.priority,
            correlation_score=record.correlation_score,
            component_scores=record.component_scores_json,
            first_sequence_number=record.first_sequence_number,
            latest_sequence_number=record.latest_sequence_number,
            first_observed_at=record.first_observed_at.replace(
                tzinfo=record.first_observed_at.tzinfo or UTC
            ),
            latest_observed_at=record.latest_observed_at.replace(
                tzinfo=record.latest_observed_at.tzinfo or UTC
            ),
            primary_user_id=record.primary_user_id,
            primary_device_id=record.primary_device_id,
            involved_asset_ids=record.involved_asset_ids_json,
            observed_tactic_ids=record.observed_tactic_ids_json,
            observed_technique_ids=record.observed_technique_ids_json,
            evidence_count=record.evidence_count,
            correlation_engine_version=record.correlation_engine_version,
            synthetic=True,
            created_at=record.created_at.replace(tzinfo=record.created_at.tzinfo or UTC),
            updated_at=record.updated_at.replace(tzinfo=record.updated_at.tzinfo or UTC),
        )


correlation_service = CorrelationService()
