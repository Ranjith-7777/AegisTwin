from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class SystemState(Base):
    __tablename__ = "system_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_name: Mapped[str] = mapped_column(String(100), nullable=False)
    simulation_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    operational: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class SimulationScenarioRecord(Base):
    __tablename__ = "simulation_scenarios"

    scenario_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    steps: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    runs: Mapped[list[SimulationRunRecord]] = relationship(back_populates="scenario")


class SimulationRunRecord(Base):
    __tablename__ = "simulation_runs"

    simulation_run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(
        ForeignKey("simulation_scenarios.scenario_id"), nullable=False, index=True
    )
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    playback_speed: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    scenario: Mapped[SimulationScenarioRecord] = relationship(back_populates="runs")
    events: Mapped[list[TelemetryEventRecord]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="TelemetryEventRecord.timestamp",
    )


class TelemetryEventRecord(Base):
    __tablename__ = "telemetry_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    simulation_run_id: Mapped[str] = mapped_column(
        ForeignKey("simulation_runs.simulation_run_id"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    destination_id: Mapped[str | None] = mapped_column(String(100))
    user_id: Mapped[str | None] = mapped_column(String(100), index=True)
    device_id: Mapped[str | None] = mapped_column(String(100))
    source_ip: Mapped[str | None] = mapped_column(String(45))
    destination_ip: Mapped[str | None] = mapped_column(String(45))
    privilege_level: Mapped[str | None] = mapped_column(String(30))
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bytes_transferred: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    process_name: Mapped[str | None] = mapped_column(String(120))
    event_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    run: Mapped[SimulationRunRecord] = relationship(back_populates="events")


class DetectionModelRecord(Base):
    __tablename__ = "detection_models"

    model_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    model_type: Mapped[str] = mapped_column(String(60), nullable=False)
    model_version: Mapped[str] = mapped_column(String(30), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    calibration_version: Mapped[str] = mapped_column(String(30), nullable=False)
    calibration_method: Mapped[str] = mapped_column(
        String(60), nullable=False, default="empirical-quantile-v1"
    )
    artifact_path: Mapped[str] = mapped_column(String(500), nullable=False)
    configuration_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    dataset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    random_state: Mapped[int] = mapped_column(Integer, nullable=False)
    target_false_positive_rate: Mapped[float] = mapped_column(Float, nullable=False)
    calibrated_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_percentile: Mapped[float] = mapped_column(Float, nullable=False)
    training_event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    validation_event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AnomalyAssessmentRecord(Base):
    __tablename__ = "anomaly_assessments"
    __table_args__ = (UniqueConstraint("model_id", "event_id", name="uq_assessment_model_event"),)

    assessment_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    model_id: Mapped[str] = mapped_column(
        ForeignKey("detection_models.model_id"), nullable=False, index=True
    )
    simulation_run_id: Mapped[str] = mapped_column(
        ForeignKey("simulation_runs.simulation_run_id"), nullable=False, index=True
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("telemetry_events.event_id"), nullable=False, index=True
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    contributing_signals_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    component_scores_json: Mapped[dict[str, float]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ModelEvaluationRecord(Base):
    __tablename__ = "model_evaluations"

    evaluation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    model_id: Mapped[str] = mapped_column(
        ForeignKey("detection_models.model_id"), nullable=False, index=True
    )
    configuration_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    normal_event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    suspicious_scenario_event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    true_positive: Mapped[int] = mapped_column(Integer, nullable=False)
    false_positive: Mapped[int] = mapped_column(Integer, nullable=False)
    true_negative: Mapped[int] = mapped_column(Integer, nullable=False)
    false_negative: Mapped[int] = mapped_column(Integer, nullable=False)
    precision: Mapped[float] = mapped_column(Float, nullable=False)
    recall: Mapped[float] = mapped_column(Float, nullable=False)
    f1_score: Mapped[float] = mapped_column(Float, nullable=False)
    false_positive_rate: Mapped[float] = mapped_column(Float, nullable=False)
    roc_auc: Mapped[float | None] = mapped_column(Float)
    average_precision: Mapped[float | None] = mapped_column(Float)
    baseline_metrics_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(
        String(30), nullable=False, default="synthetic-behaviour-v1"
    )
    calibration_method: Mapped[str] = mapped_column(
        String(60), nullable=False, default="empirical-quantile-v1"
    )
    evaluation_label_mode: Mapped[str] = mapped_column(
        String(60), nullable=False, default="scenario-wide"
    )
    event_level_metrics_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    scenario_wide_metrics_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    run_level_metrics_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    per_step_metrics_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    score_distribution_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    calibration_comparison_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    pure_isolation_metrics_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    hybrid_metrics_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    diagnostic_report_json: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MitreTechniqueRecord(Base):
    __tablename__ = "mitre_technique_catalogue"
    technique_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    tactics_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    mapping_conditions: Mapped[str] = mapped_column(String(800), nullable=False)
    catalogue_version: Mapped[str] = mapped_column(String(30), nullable=False)
    source_name: Mapped[str] = mapped_column(String(80), nullable=False)
    reference_date: Mapped[str] = mapped_column(String(10), nullable=False)
    synthetic_demo_applicable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TechniqueObservationRecord(Base):
    __tablename__ = "technique_observations"
    __table_args__ = (
        UniqueConstraint(
            "simulation_run_id",
            "model_id",
            "event_id",
            "technique_id",
            "mapper_version",
            name="uq_technique_observation",
        ),
    )
    mapping_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    technique_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    technique_name: Mapped[str] = mapped_column(String(120), nullable=False)
    simulation_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    mapping_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_fields_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    rationale: Mapped[str] = mapped_column(String(800), nullable=False)
    tactic: Mapped[str] = mapped_column(String(60), nullable=False)
    mapper_version: Mapped[str] = mapped_column(String(30), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class IncidentCandidateRecord(Base):
    __tablename__ = "incident_candidates"
    __table_args__ = (
        UniqueConstraint(
            "simulation_run_id",
            "model_id",
            "correlation_engine_version",
            name="uq_incident_run_model_engine",
        ),
    )
    incident_candidate_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    simulation_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(String(800), nullable=False)
    correlation_state: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    correlation_score: Mapped[float] = mapped_column(Float, nullable=False)
    component_scores_json: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    first_sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    latest_sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latest_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    primary_user_id: Mapped[str | None] = mapped_column(String(100))
    primary_device_id: Mapped[str | None] = mapped_column(String(100))
    involved_asset_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    observed_tactic_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    observed_technique_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    correlation_engine_version: Mapped[str] = mapped_column(String(30), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IncidentEvidenceRecord(Base):
    __tablename__ = "incident_evidence"
    __table_args__ = (
        UniqueConstraint("incident_candidate_id", "event_id", name="uq_incident_event"),
    )
    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    incident_candidate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    assessment_id: Mapped[str | None] = mapped_column(String(36))
    technique_mapping_id: Mapped[str | None] = mapped_column(String(36))
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(60), nullable=False)
    contribution_score: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(String(800), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class IncidentCandidateSnapshotRecord(Base):
    __tablename__ = "incident_candidate_snapshots"
    __table_args__ = (
        UniqueConstraint("incident_candidate_id", "sequence_number", name="uq_incident_snapshot"),
    )
    snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    incident_candidate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProgressionCatalogueEntryRecord(Base):
    __tablename__ = "progression_catalogue_entries"
    entry_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    source_technique_id: Mapped[str | None] = mapped_column(String(20))
    destination_technique_id: Mapped[str | None] = mapped_column(String(20))
    source_tactic: Mapped[str | None] = mapped_column(String(60))
    destination_tactic: Mapped[str] = mapped_column(String(60), nullable=False)
    rationale: Mapped[str] = mapped_column(String(800), nullable=False)
    prerequisites_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    contradictions_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    transition_weight: Mapped[float] = mapped_column(Float, nullable=False)
    catalogue_version: Mapped[str] = mapped_column(String(40), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PredictionSnapshotRecord(Base):
    __tablename__ = "prediction_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "simulation_run_id",
            "model_id",
            "predictor_version",
            "through_sequence_number",
            name="uq_prediction_snapshot",
        ),
    )
    prediction_snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    simulation_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    incident_candidate_id: Mapped[str | None] = mapped_column(String(36), index=True)
    through_sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    predictor_version: Mapped[str] = mapped_column(String(40), nullable=False)
    progression_catalogue_version: Mapped[str] = mapped_column(String(40), nullable=False)
    prediction_state: Mapped[str] = mapped_column(String(30), nullable=False)
    current_stage_estimate: Mapped[str] = mapped_column(String(60), nullable=False)
    current_tactic_estimate: Mapped[str] = mapped_column(String(60), nullable=False)
    observed_technique_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    observed_tactic_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    candidate_hypothesis_count: Mapped[int] = mapped_column(Integer, nullable=False)
    insufficient_evidence_reason: Mapped[str | None] = mapped_column(String(500))
    supporting_evidence_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PredictionHypothesisRecord(Base):
    __tablename__ = "prediction_hypotheses"
    __table_args__ = (
        UniqueConstraint(
            "prediction_snapshot_id", "hypothesis_type", "rank", name="uq_prediction_hypothesis"
        ),
    )
    hypothesis_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    prediction_snapshot_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    hypothesis_type: Mapped[str] = mapped_column(String(30), nullable=False)
    predicted_technique_id: Mapped[str | None] = mapped_column(String(20))
    predicted_technique_name: Mapped[str | None] = mapped_column(String(120))
    predicted_tactic: Mapped[str | None] = mapped_column(String(60))
    predicted_asset_id: Mapped[str | None] = mapped_column(String(100))
    predicted_objective: Mapped[str | None] = mapped_column(String(60))
    prediction_score: Mapped[float] = mapped_column(Float, nullable=False)
    component_scores_json: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    prerequisite_evidence_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    contradictory_evidence_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    rationale: Mapped[str] = mapped_column(String(1000), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PredictionEvaluationRecord(Base):
    __tablename__ = "prediction_evaluations"
    evaluation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    simulation_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(36), nullable=False)
    predictor_version: Mapped[str] = mapped_column(String(40), nullable=False)
    metrics_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    baseline_metrics_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    truth_manifest_version: Mapped[str] = mapped_column(String(40), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResponsePlaybookRecord(Base):
    __tablename__ = "response_playbook_catalogue"
    playbook_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    playbook_version: Mapped[str] = mapped_column(String(30), nullable=False)
    catalogue_version: Mapped[str] = mapped_column(String(30), nullable=False)
    definition_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ResponseAnalysisRecord(Base):
    __tablename__ = "response_analyses"
    __table_args__ = (
        UniqueConstraint(
            "simulation_run_id",
            "model_id",
            "incident_candidate_id",
            "through_sequence_number",
            "response_engine_version",
            name="uq_response_analysis",
        ),
    )
    response_analysis_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    simulation_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    incident_candidate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    prediction_snapshot_id: Mapped[str | None] = mapped_column(String(36))
    through_sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    response_engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    recommendation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResponseRecommendationRecord(Base):
    __tablename__ = "response_recommendations"
    __table_args__ = (
        UniqueConstraint(
            "response_analysis_id",
            "playbook_id",
            "target_type",
            "target_id",
            name="uq_response_recommendation_target",
        ),
    )
    recommendation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    response_analysis_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    simulation_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(36), nullable=False)
    incident_candidate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    prediction_snapshot_id: Mapped[str | None] = mapped_column(String(36))
    through_sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    playbook_id: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[str] = mapped_column(String(220), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    recommendation_score: Mapped[float] = mapped_column(Float, nullable=False)
    component_scores_json: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    penalties_json: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    required_approval_tier: Mapped[str] = mapped_column(String(40), nullable=False)
    recommendation_state: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_summary_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    rationale: Mapped[str] = mapped_column(String(1000), nullable=False)
    warnings_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResponseImpactSimulationRecord(Base):
    __tablename__ = "response_impact_simulations"
    simulation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    recommendation_id: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, index=True
    )
    simulation_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    through_sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    base_topology_version: Mapped[str] = mapped_column(String(60), nullable=False)
    simulation_engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[str] = mapped_column(String(220), nullable=False)
    changed_node_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    changed_edge_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    paths_before_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    paths_after_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    correlated_paths_interrupted: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_paths_interrupted: Mapped[int] = mapped_column(Integer, nullable=False)
    sensitive_assets_reachable_before: Mapped[int] = mapped_column(Integer, nullable=False)
    sensitive_assets_reachable_after: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_relationships_affected: Mapped[int] = mapped_column(Integer, nullable=False)
    affected_asset_count: Mapped[int] = mapped_column(Integer, nullable=False)
    affected_edge_count: Mapped[int] = mapped_column(Integer, nullable=False)
    interruption_score: Mapped[float] = mapped_column(Float, nullable=False)
    residual_exposure_score: Mapped[float] = mapped_column(Float, nullable=False)
    operational_disruption_score: Mapped[float] = mapped_column(Float, nullable=False)
    blast_radius: Mapped[str] = mapped_column(String(30), nullable=False)
    reversibility: Mapped[str] = mapped_column(String(30), nullable=False)
    warnings_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResponseOrchestrationRecord(Base):
    __tablename__ = "response_orchestrations"
    __table_args__ = (
        UniqueConstraint(
            "simulation_run_id",
            "model_id",
            "incident_candidate_id",
            "selected_recommendation_id",
            "through_sequence_number",
            name="uq_response_orchestration_input",
        ),
    )
    orchestration_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    simulation_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    incident_candidate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    through_sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    orchestration_version: Mapped[str] = mapped_column(String(40), nullable=False)
    current_state: Mapped[str] = mapped_column(String(60), nullable=False)
    selected_recommendation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    required_approval_tier: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ResponsePlanStepRecord(Base):
    __tablename__ = "response_plan_steps"
    __table_args__ = (UniqueConstraint("orchestration_id", "step_number", name="uq_plan_step"),)
    plan_step_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    orchestration_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    playbook_id: Mapped[str] = mapped_column(String(80), nullable=False)
    recommendation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[str] = mapped_column(String(220), nullable=False)
    required_approval_tier: Mapped[str] = mapped_column(String(40), nullable=False)
    reversibility: Mapped[str] = mapped_column(String(30), nullable=False)
    rationale: Mapped[str] = mapped_column(String(1000), nullable=False)
    expected_mutation_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    current_status: Mapped[str] = mapped_column(String(50), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AgentDecisionRecord(Base):
    __tablename__ = "agent_decisions"
    agent_decision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    orchestration_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(80), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(40), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(80), nullable=False)
    input_reference_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    output_summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    decision: Mapped[str] = mapped_column(String(80), nullable=False)
    ranking_score: Mapped[float | None] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(String(1000), nullable=False)
    warnings_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    next_agent: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ApprovalRequestRecord(Base):
    __tablename__ = "approval_requests"
    approval_request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    orchestration_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    plan_step_id: Mapped[str | None] = mapped_column(String(36))
    required_role: Mapped[str] = mapped_column(String(30), nullable=False)
    approval_state: Mapped[str] = mapped_column(String(30), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(String(120))
    decision_reason: Mapped[str | None] = mapped_column(String(1000))
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SyntheticExecutionRecord(Base):
    __tablename__ = "synthetic_executions"
    __table_args__ = (
        UniqueConstraint("orchestration_id", "plan_step_id", name="uq_execution_step"),
    )
    execution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    orchestration_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    plan_step_id: Mapped[str] = mapped_column(String(36), nullable=False)
    playbook_id: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[str] = mapped_column(String(220), nullable=False)
    execution_state: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mutation_summary_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    changed_node_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    changed_edge_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    pre_execution_state_reference: Mapped[str] = mapped_column(String(80), nullable=False)
    post_execution_state_reference: Mapped[str | None] = mapped_column(String(80))
    simulated_failure_reason: Mapped[str | None] = mapped_column(String(300))
    reversible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ResponseVerificationRecord(Base):
    __tablename__ = "response_verifications"
    verification_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    orchestration_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    execution_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    verification_status: Mapped[str] = mapped_column(String(50), nullable=False)
    metrics_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    unintended_effects_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class RollbackRecord(Base):
    __tablename__ = "rollback_records"
    rollback_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    orchestration_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    execution_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(120), nullable=False)
    approval_request_id: Mapped[str | None] = mapped_column(String(36))
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    restored_state_reference: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_summary_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AuditEventRecord(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("orchestration_id", "sequence_number", name="uq_audit_sequence"),
    )
    audit_event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    orchestration_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    previous_event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
