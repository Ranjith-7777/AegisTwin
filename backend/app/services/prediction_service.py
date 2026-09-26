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
    PredictionHypothesisRecord,
    PredictionSnapshotRecord,
    SimulationRunRecord,
    TechniqueObservationRecord,
)
from app.events.envelope import DomainEvent, PredictionGeneratedPayload
from app.events.registry import get_event_bus
from app.events.types import EventType
from app.schemas.prediction import (
    PredictionAnalysisResult,
    PredictionHypothesis,
    PredictionSnapshot,
)
from app.schemas.telemetry import TelemetryEvent
from app.services.infrastructure_service import inventory_service
from app.services.progression_catalogue_service import (
    ENTRIES,
    PROGRESSION_CATALOGUE_VERSION,
    ProgressionEntry,
    progression_catalogue_service,
)
from app.services.telemetry_service import telemetry_service

PREDICTOR_VERSION = "hybrid-progression-v1"
PREDICTION_NAMESPACE = UUID("95119afd-3d27-4775-866a-c0052937a170")
COMPONENT_WEIGHTS = {
    "technique_transition": 0.25,
    "tactic_progression": 0.15,
    "infrastructure_reachability": 0.20,
    "anomaly_context": 0.15,
    "incident_coherence": 0.15,
    "prerequisite_satisfaction": 0.10,
}
TECHNIQUE_NAMES = {
    "T1078": "Valid Accounts",
    "T1098": "Account Manipulation",
    "T1021": "Remote Services",
    "T1041": "Exfiltration Over C2 Channel",
    "T1567": "Exfiltration Over Web Service",
}


class PredictionService:
    def analyze(
        self, session: Session, run_id: str, model_id: str, force: bool, top_k: int
    ) -> PredictionAnalysisResult:
        if session.get(SimulationRunRecord, run_id) is None:
            raise ApplicationError(
                "SIMULATION_RUN_NOT_FOUND", "The simulation run was not found.", 404
            )
        if session.get(DetectionModelRecord, model_id) is None:
            raise ApplicationError(
                "DETECTION_MODEL_NOT_FOUND", "The detection model was not found.", 404
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
                "Complete assessments are required before prediction.",
                409,
            )
        candidate = session.scalar(
            select(IncidentCandidateRecord).where(
                IncidentCandidateRecord.simulation_run_id == run_id,
                IncidentCandidateRecord.model_id == model_id,
            )
        )
        if candidate is None:
            raise ApplicationError(
                "CORRELATION_NOT_READY",
                "Correlation analysis must complete before prediction.",
                409,
            )
        existing = list(
            session.scalars(
                select(PredictionSnapshotRecord).where(
                    PredictionSnapshotRecord.simulation_run_id == run_id,
                    PredictionSnapshotRecord.model_id == model_id,
                    PredictionSnapshotRecord.predictor_version == PREDICTOR_VERSION,
                )
            )
        )
        if existing and not force:
            count = int(
                session.scalar(
                    select(func.count())
                    .select_from(PredictionHypothesisRecord)
                    .where(
                        PredictionHypothesisRecord.prediction_snapshot_id.in_(
                            [item.prediction_snapshot_id for item in existing]
                        )
                    )
                )
                or 0
            )
            return self._result(run_id, model_id, len(existing), count, top_k, False)
        if force and existing:
            ids = [item.prediction_snapshot_id for item in existing]
            session.execute(
                delete(PredictionHypothesisRecord).where(
                    PredictionHypothesisRecord.prediction_snapshot_id.in_(ids)
                )
            )
            session.execute(
                delete(PredictionSnapshotRecord).where(
                    PredictionSnapshotRecord.prediction_snapshot_id.in_(ids)
                )
            )
        progression_catalogue_service.ensure(session)
        observations = list(
            session.scalars(
                select(TechniqueObservationRecord)
                .where(
                    TechniqueObservationRecord.simulation_run_id == run_id,
                    TechniqueObservationRecord.model_id == model_id,
                )
                .order_by(TechniqueObservationRecord.sequence_number)
            )
        )
        incident_snapshots = {
            item.sequence_number: item.snapshot_json
            for item in session.scalars(
                select(IncidentCandidateSnapshotRecord).where(
                    IncidentCandidateSnapshotRecord.incident_candidate_id
                    == candidate.incident_candidate_id
                )
            )
        }
        hypothesis_count = 0
        for sequence in range(1, len(events) + 1):
            available_events = events[:sequence]
            available_assessments = assessments[:sequence]
            available_observations = [
                item for item in observations if item.sequence_number <= sequence
            ]
            incident = self._latest_incident(incident_snapshots, sequence)
            snapshot_id = str(
                uuid5(
                    PREDICTION_NAMESPACE,
                    f"snapshot:{run_id}:{model_id}:{PREDICTOR_VERSION}:{sequence}",
                )
            )
            observed_techniques = list(
                dict.fromkeys(item.technique_id for item in available_observations)
            )
            observed_tactics = list(dict.fromkeys(item.tactic for item in available_observations))
            stage, tactic, support = self._stage(
                available_events, observed_techniques, observed_tactics
            )
            eligible = len(available_observations) > 0 and sequence < len(events)
            hypotheses = (
                self._hypotheses(
                    snapshot_id,
                    available_events,
                    available_assessments,
                    available_observations,
                    incident,
                    top_k,
                )
                if eligible
                else []
            )
            state = (
                "active"
                if len(available_observations) >= 2
                else "preliminary"
                if eligible
                else "insufficient_evidence"
            )
            snapshot = PredictionSnapshotRecord(
                prediction_snapshot_id=snapshot_id,
                simulation_run_id=run_id,
                model_id=model_id,
                incident_candidate_id=candidate.incident_candidate_id,
                through_sequence_number=sequence,
                predictor_version=PREDICTOR_VERSION,
                progression_catalogue_version=PROGRESSION_CATALOGUE_VERSION,
                prediction_state=state,
                current_stage_estimate=stage,
                current_tactic_estimate=tactic,
                observed_technique_ids_json=observed_techniques,
                observed_tactic_ids_json=observed_tactics,
                candidate_hypothesis_count=len(hypotheses),
                insufficient_evidence_reason=None
                if eligible
                else "No causal technique progression is available yet."
                if sequence < len(events)
                else "The synthetic run has concluded.",
                supporting_evidence_json=support,
                synthetic=True,
                created_at=datetime.now(UTC),
            )
            session.add(snapshot)
            for item in hypotheses:
                session.add(item)
            hypothesis_count += len(hypotheses)
        session.flush()
        get_event_bus().publish(
            DomainEvent(
                event_type=EventType.PREDICTION_GENERATED,
                source="prediction",
                run_id=run_id,
                correlation_id=run_id,
                payload=PredictionGeneratedPayload(
                    run_id=run_id, model_id=model_id, hypothesis_count=hypothesis_count
                ),
            )
        )
        return self._result(run_id, model_id, len(events), hypothesis_count, top_k, force)

    def _hypotheses(
        self,
        snapshot_id: str,
        events: list[TelemetryEvent],
        assessments: list[AnomalyAssessmentRecord],
        observations: list[TechniqueObservationRecord],
        incident: dict[str, object] | None,
        top_k: int,
    ) -> list[PredictionHypothesisRecord]:
        latest_technique = observations[-1].technique_id
        transitions = [item for item in ENTRIES if item.source_technique_id == latest_technique]
        anomaly = sum(
            item.anomaly_score for item in assessments if item.classification == "anomalous"
        ) / max(1, len(assessments))
        raw_coherence = incident.get("correlation_score", 0.0) if incident else 0.0
        coherence = float(raw_coherence) if isinstance(raw_coherence, int | float) else 0.0
        records: list[PredictionHypothesisRecord] = []
        ranked_transitions: list[tuple[float, ProgressionEntry, dict[str, float], list[str]]] = []
        for entry in transitions:
            contradiction = self._contradictions(entry.destination_technique_id, events)
            components = {
                "technique_transition": entry.transition_weight,
                "tactic_progression": 0.85,
                "infrastructure_reachability": self._reachability_context(events),
                "anomaly_context": min(1.0, anomaly),
                "incident_coherence": min(1.0, coherence),
                "prerequisite_satisfaction": 1.0,
            }
            score = sum(
                COMPONENT_WEIGHTS[name] * value for name, value in components.items()
            ) - 0.08 * len(contradiction)
            components["contradiction_penalty"] = 0.08 * len(contradiction)
            ranked_transitions.append((max(0.0, score), entry, components, contradiction))
        for rank, (score, entry, components, contradiction) in enumerate(
            sorted(
                ranked_transitions, key=lambda item: (-item[0], item[1].destination_technique_id)
            )[:top_k],
            1,
        ):
            records.append(
                self._record(
                    snapshot_id,
                    "next_technique",
                    rank,
                    score,
                    components,
                    list(entry.prerequisites),
                    contradiction,
                    entry.rationale,
                    technique=entry.destination_technique_id,
                    technique_name=TECHNIQUE_NAMES.get(entry.destination_technique_id),
                    tactic=entry.destination_tactic,
                )
            )
        tactic_scores: dict[str, float] = {}
        for score, entry, _, _ in ranked_transitions:
            tactic_scores[entry.destination_tactic] = max(
                tactic_scores.get(entry.destination_tactic, 0.0), score
            )
        for rank, (tactic, score) in enumerate(
            sorted(tactic_scores.items(), key=lambda item: (-item[1], item[0]))[:top_k], 1
        ):
            records.append(
                self._record(
                    snapshot_id,
                    "next_tactic",
                    rank,
                    score,
                    {"tactic_progression": score, "contradiction_penalty": 0.0},
                    ["observed technique progression"],
                    [],
                    "Ranked from the local synthetic tactic progression graph.",
                    tactic=tactic,
                )
            )
        for rank, (asset, score, rationale) in enumerate(self._asset_hypotheses(events)[:top_k], 1):
            records.append(
                self._record(
                    snapshot_id,
                    "next_asset",
                    rank,
                    score,
                    {"infrastructure_reachability": score, "contradiction_penalty": 0.0},
                    ["reachable synthetic infrastructure relationship"],
                    [],
                    rationale,
                    asset=asset,
                )
            )
        for rank, (objective, score) in enumerate(self._objectives(latest_technique)[:top_k], 1):
            records.append(
                self._record(
                    snapshot_id,
                    "likely_objective",
                    rank,
                    score,
                    {
                        "technique_transition": score,
                        "incident_coherence": coherence,
                        "contradiction_penalty": 0.0,
                    },
                    [f"latest observed technique {latest_technique}"],
                    [],
                    "Cautious synthetic objective derived from observed progression evidence.",
                    objective=objective,
                )
            )
        return records

    @staticmethod
    def _record(
        snapshot_id: str,
        kind: str,
        rank: int,
        score: float,
        components: dict[str, float],
        prerequisite: list[str],
        contradiction: list[str],
        rationale: str,
        *,
        technique: str | None = None,
        technique_name: str | None = None,
        tactic: str | None = None,
        asset: str | None = None,
        objective: str | None = None,
    ) -> PredictionHypothesisRecord:
        return PredictionHypothesisRecord(
            hypothesis_id=str(
                uuid5(PREDICTION_NAMESPACE, f"hypothesis:{snapshot_id}:{kind}:{rank}")
            ),
            prediction_snapshot_id=snapshot_id,
            rank=rank,
            hypothesis_type=kind,
            predicted_technique_id=technique,
            predicted_technique_name=technique_name,
            predicted_tactic=tactic,
            predicted_asset_id=asset,
            predicted_objective=objective,
            prediction_score=score,
            component_scores_json=components,
            prerequisite_evidence_json=prerequisite,
            contradictory_evidence_json=contradiction,
            rationale=rationale,
            synthetic=True,
        )

    @staticmethod
    def _stage(
        events: list[TelemetryEvent], techniques: list[str], tactics: list[str]
    ) -> tuple[str, str, list[str]]:
        latest = techniques[-1] if techniques else None
        mapping = {
            "T1110.001": ("authentication_pressure", "Credential Access"),
            "T1078": ("credential_use", "Initial Access"),
            "T1098": ("account_modification", "Persistence"),
            "T1021": ("lateral_access", "Lateral Movement"),
            "T1041": ("collection_or_transfer", "Exfiltration"),
            "T1567": ("collection_or_transfer", "Exfiltration"),
        }
        if latest in mapping:
            stage, tactic = mapping[latest]
        elif events and events[-1].destination_id == "cloud-database-01":
            stage, tactic = "sensitive_resource_access", "Collection"
        else:
            stage, tactic = "normal_activity", tactics[-1] if tactics else "insufficient_evidence"
        if events and events[-1].action.value == "logout":
            stage = "session_conclusion"
        return (
            stage,
            tactic,
            [f"observed technique {item}" for item in techniques]
            or ["routine synthetic telemetry only"],
        )

    @staticmethod
    def _latest_incident(
        snapshots: dict[int, dict[str, object]], sequence: int
    ) -> dict[str, object] | None:
        eligible = [key for key in snapshots if key <= sequence]
        return snapshots[max(eligible)] if eligible else None

    @staticmethod
    def _contradictions(technique: str, events: list[TelemetryEvent]) -> list[str]:
        metadata = [item.metadata for item in events]
        if technique == "T1567" and not any(
            item.get("channel_type") == "synthetic_web_service" for item in metadata
        ):
            return ["explicit synthetic web-service channel not yet observed"]
        if technique == "T1041" and not any(
            item.get("channel_type") == "synthetic_c2" for item in metadata
        ):
            return ["explicit synthetic C2 channel not observed"]
        if technique == "T1021" and not any(
            isinstance(item.get("remote_service"), str) for item in metadata
        ):
            return ["remote-service metadata not yet observed"]
        return []

    @staticmethod
    def _reachability_context(events: list[TelemetryEvent]) -> float:
        if not events:
            return 0.0
        current = events[-1].destination_id or events[-1].source_id
        try:
            return 1.0 if inventory_service.get_asset(current).relationships else 0.2
        except KeyError:
            return 0.0

    @staticmethod
    def _asset_hypotheses(events: list[TelemetryEvent]) -> list[tuple[str, float, str]]:
        if not events:
            return []
        current = events[-1].destination_id or events[-1].source_id
        try:
            relationships = inventory_service.get_asset(current).relationships
        except KeyError:
            relationships = ()
        visited = {
            asset for event in events for asset in (event.source_id, event.destination_id) if asset
        }
        candidates = []
        for asset_id in relationships:
            asset = inventory_service.get_asset(asset_id)
            sensitivity = {"critical": 0.25, "high": 0.18, "medium": 0.10, "low": 0.05}[
                asset.criticality.value
            ]
            novelty = 0.0 if asset_id in visited else 0.15
            candidates.append(
                (
                    asset_id,
                    min(1.0, 0.60 + sensitivity + novelty),
                    f"Reachable from {current} through one documented synthetic relationship.",
                )
            )
        return sorted(candidates, key=lambda item: (-item[1], item[0]))

    @staticmethod
    def _objectives(latest: str) -> list[tuple[str, float]]:
        mapping = {
            "T1110.001": [("maintain_access", 0.55), ("expand_access", 0.45)],
            "T1078": [("expand_access", 0.65), ("maintain_access", 0.55)],
            "T1098": [("expand_access", 0.72), ("reach_sensitive_resource", 0.60)],
            "T1021": [("reach_sensitive_resource", 0.75), ("collect_data", 0.58)],
            "T1041": [("transfer_data", 0.85)],
            "T1567": [("transfer_data", 0.85)],
        }
        return mapping.get(latest, [("insufficient_evidence", 0.0)])

    @staticmethod
    def _result(
        run_id: str, model_id: str, snapshots: int, hypotheses: int, top_k: int, force: bool
    ) -> PredictionAnalysisResult:
        return PredictionAnalysisResult(
            simulation_run_id=run_id,
            model_id=model_id,
            snapshot_count=snapshots,
            hypothesis_count=hypotheses,
            predictor_version=PREDICTOR_VERSION,
            progression_catalogue_version=PROGRESSION_CATALOGUE_VERSION,
            top_k=top_k,
            force_reanalyze=force,
            synthetic=True,
        )

    def snapshot_schema(
        self, session: Session, record: PredictionSnapshotRecord, include_hypotheses: bool = True
    ) -> PredictionSnapshot:
        hypotheses = (
            list(
                session.scalars(
                    select(PredictionHypothesisRecord)
                    .where(
                        PredictionHypothesisRecord.prediction_snapshot_id
                        == record.prediction_snapshot_id
                    )
                    .order_by(
                        PredictionHypothesisRecord.hypothesis_type, PredictionHypothesisRecord.rank
                    )
                )
            )
            if include_hypotheses
            else []
        )
        return PredictionSnapshot(
            prediction_snapshot_id=record.prediction_snapshot_id,
            simulation_run_id=record.simulation_run_id,
            model_id=record.model_id,
            incident_candidate_id=record.incident_candidate_id,
            through_sequence_number=record.through_sequence_number,
            predictor_version=record.predictor_version,
            progression_catalogue_version=record.progression_catalogue_version,
            prediction_state=record.prediction_state,
            current_stage_estimate=record.current_stage_estimate,
            current_tactic_estimate=record.current_tactic_estimate,
            observed_technique_ids=record.observed_technique_ids_json,
            observed_tactic_ids=record.observed_tactic_ids_json,
            candidate_hypothesis_count=record.candidate_hypothesis_count,
            insufficient_evidence_reason=record.insufficient_evidence_reason,
            supporting_evidence=record.supporting_evidence_json,
            hypotheses=[self.hypothesis_schema(item) for item in hypotheses],
            synthetic=True,
            created_at=record.created_at.replace(tzinfo=record.created_at.tzinfo or UTC),
        )

    @staticmethod
    def hypothesis_schema(item: PredictionHypothesisRecord) -> PredictionHypothesis:
        return PredictionHypothesis(
            hypothesis_id=item.hypothesis_id,
            prediction_snapshot_id=item.prediction_snapshot_id,
            rank=item.rank,
            hypothesis_type=item.hypothesis_type,
            predicted_technique_id=item.predicted_technique_id,
            predicted_technique_name=item.predicted_technique_name,
            predicted_tactic=item.predicted_tactic,
            predicted_asset_id=item.predicted_asset_id,
            predicted_objective=item.predicted_objective,
            prediction_score=item.prediction_score,
            component_scores=item.component_scores_json,
            prerequisite_evidence=item.prerequisite_evidence_json,
            contradictory_evidence=item.contradictory_evidence_json,
            rationale=item.rationale,
            synthetic=True,
        )


prediction_service = PredictionService()
