from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
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
