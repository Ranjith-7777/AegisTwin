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
