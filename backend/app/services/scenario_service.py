from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import SimulationScenarioRecord
from app.schemas.simulation import ScenarioStep, SimulationScenario
from app.schemas.telemetry import (
    EventAction,
    EventOutcome,
    EventType,
    PrivilegeLevel,
    Severity,
    SourceType,
)


def _step(
    sequence: int,
    offset_seconds: int,
    description: str,
    event_type: EventType,
    action: EventAction,
    outcome: EventOutcome,
    severity: Severity,
    source_type: SourceType,
    source_id: str,
    destination_id: str | None = None,
    user_id: str | None = None,
    device_id: str | None = None,
    privilege_level: PrivilegeLevel | None = None,
    process_name: str | None = None,
    metadata: dict[str, object] | None = None,
) -> ScenarioStep:
    return ScenarioStep(
        sequence=sequence,
        offset_seconds=offset_seconds,
        description=description,
        event_type=event_type,
        action=action,
        outcome=outcome,
        severity=severity,
        source_type=source_type,
        source_id=source_id,
        destination_id=destination_id,
        user_id=user_id,
        device_id=device_id,
        privilege_level=privilege_level,
        process_name=process_name,
        metadata=metadata or {},
    )


SCENARIOS: tuple[SimulationScenario, ...] = (
    SimulationScenario(
        scenario_id="normal-operations",
        name="Normal Operations",
        description="Routine synthetic office-hours activity across the examination environment.",
        steps=[
            _step(
                1,
                0,
                "Normal office-hours login",
                EventType.AUTHENTICATION,
                EventAction.LOGIN,
                EventOutcome.SUCCESS,
                Severity.INFORMATIONAL,
                SourceType.DEVICE,
                "employee-laptop-01",
                "authentication-server-01",
                "synthetic-user-01",
                "employee-laptop-01",
                PrivilegeLevel.STANDARD,
                metadata={"office_hours": True, "device_known": True},
            ),
            _step(
                2,
                45,
                "Portal access",
                EventType.PORTAL_ACCESS,
                EventAction.ACCESS,
                EventOutcome.ALLOWED,
                Severity.INFORMATIONAL,
                SourceType.DEVICE,
                "employee-laptop-01",
                "examination-portal-01",
                "synthetic-user-01",
                "employee-laptop-01",
                PrivilegeLevel.STANDARD,
            ),
            _step(
                3,
                90,
                "Routine application request",
                EventType.APPLICATION_REQUEST,
                EventAction.REQUEST,
                EventOutcome.SUCCESS,
                Severity.INFORMATIONAL,
                SourceType.SERVICE,
                "examination-portal-01",
                "application-server-01",
                "synthetic-user-01",
                "employee-laptop-01",
                PrivilegeLevel.STANDARD,
                "synthetic-portal-worker",
            ),
            _step(
                4,
                135,
                "Normal database query",
                EventType.DATABASE_QUERY,
                EventAction.QUERY,
                EventOutcome.SUCCESS,
                Severity.LOW,
                SourceType.SERVER,
                "application-server-01",
                "examination-database-01",
                "synthetic-user-01",
                "employee-laptop-01",
                PrivilegeLevel.SERVICE,
                "synthetic-query-service",
                {"query_category": "candidate_summary"},
            ),
            _step(
                5,
                180,
                "Small data transfer",
                EventType.DATA_TRANSFER,
                EventAction.TRANSFER,
                EventOutcome.COMPLETED,
                Severity.LOW,
                SourceType.SERVER,
                "application-server-01",
                "employee-laptop-01",
                "synthetic-user-01",
                "employee-laptop-01",
                PrivilegeLevel.STANDARD,
            ),
            _step(
                6,
                240,
                "Normal logout",
                EventType.SESSION,
                EventAction.LOGOUT,
                EventOutcome.SUCCESS,
                Severity.INFORMATIONAL,
                SourceType.DEVICE,
                "employee-laptop-01",
                "authentication-server-01",
                "synthetic-user-01",
                "employee-laptop-01",
                PrivilegeLevel.STANDARD,
            ),
        ],
    ),
    SimulationScenario(
        scenario_id="credential-compromise",
        name="Credential Compromise Exercise",
        description=(
            "Suspicious-looking but entirely synthetic credential and access exercise telemetry."
        ),
        steps=[
            _step(
                1,
                0,
                "Repeated failed authentication",
                EventType.AUTHENTICATION,
                EventAction.LOGIN,
                EventOutcome.FAILURE,
                Severity.MEDIUM,
                SourceType.DEVICE,
                "employee-laptop-01",
                "authentication-server-01",
                "synthetic-user-01",
                "synthetic-unseen-device",
                PrivilegeLevel.STANDARD,
                metadata={"office_hours": False, "device_known": False},
            ),
            _step(
                2,
                60,
                "Successful login at an unusual hour",
                EventType.AUTHENTICATION,
                EventAction.LOGIN,
                EventOutcome.SUCCESS,
                Severity.MEDIUM,
                SourceType.DEVICE,
                "employee-laptop-01",
                "authentication-server-01",
                "synthetic-user-01",
                "synthetic-unseen-device",
                PrivilegeLevel.STANDARD,
                metadata={"office_hours": False, "device_known": False},
            ),
            _step(
                3,
                95,
                "Previously unseen synthetic device observed",
                EventType.SESSION,
                EventAction.ACCESS,
                EventOutcome.ALLOWED,
                Severity.MEDIUM,
                SourceType.DEVICE,
                "employee-laptop-01",
                "examination-portal-01",
                "synthetic-user-01",
                "synthetic-unseen-device",
                PrivilegeLevel.STANDARD,
                metadata={"device_known": False, "synthetic_observation": True},
            ),
            _step(
                4,
                145,
                "Privilege-level change",
                EventType.PRIVILEGE_CHANGE,
                EventAction.CHANGE_PRIVILEGE,
                EventOutcome.SUCCESS,
                Severity.HIGH,
                SourceType.SERVICE,
                "authentication-server-01",
                "employee-laptop-01",
                "synthetic-user-01",
                "synthetic-unseen-device",
                PrivilegeLevel.ELEVATED,
                metadata={"previous_privilege": "standard"},
            ),
            _step(
                5,
                195,
                "Access to application server",
                EventType.APPLICATION_REQUEST,
                EventAction.ACCESS,
                EventOutcome.ALLOWED,
                Severity.MEDIUM,
                SourceType.DEVICE,
                "employee-laptop-01",
                "application-server-01",
                "synthetic-user-01",
                "synthetic-unseen-device",
                PrivilegeLevel.ELEVATED,
                "synthetic-client",
            ),
            _step(
                6,
                245,
                "Internal connection toward examination database",
                EventType.INTERNAL_CONNECTION,
                EventAction.CONNECT,
                EventOutcome.ALLOWED,
                Severity.HIGH,
                SourceType.SERVER,
                "application-server-01",
                "examination-database-01",
                "synthetic-user-01",
                "synthetic-unseen-device",
                PrivilegeLevel.ELEVATED,
                "synthetic-db-client",
            ),
            _step(
                7,
                310,
                "Large synthetic outbound transfer",
                EventType.DATA_TRANSFER,
                EventAction.TRANSFER,
                EventOutcome.COMPLETED,
                Severity.HIGH,
                SourceType.DATABASE,
                "examination-database-01",
                "simulation-egress-sink-01",
                "synthetic-user-01",
                "synthetic-unseen-device",
                PrivilegeLevel.ELEVATED,
                "synthetic-transfer-client",
                {"synthetic_boundary": True, "destination_class": "simulation_sink"},
            ),
        ],
    ),
)


class ScenarioService:
    def __init__(self) -> None:
        self._definitions = {scenario.scenario_id: scenario for scenario in SCENARIOS}

    def ensure_persisted(self, session: Session) -> None:
        for scenario in SCENARIOS:
            if session.get(SimulationScenarioRecord, scenario.scenario_id) is None:
                session.add(
                    SimulationScenarioRecord(
                        scenario_id=scenario.scenario_id,
                        name=scenario.name,
                        description=scenario.description,
                        steps=[step.model_dump(mode="json") for step in scenario.steps],
                        synthetic=True,
                        created_at=datetime(2026, 7, 21, tzinfo=UTC),
                    )
                )
        session.flush()

    def list_scenarios(self, session: Session) -> list[SimulationScenario]:
        self.ensure_persisted(session)
        return list(SCENARIOS)

    def get_scenario(self, session: Session, scenario_id: str) -> SimulationScenario:
        self.ensure_persisted(session)
        scenario = self._definitions.get(scenario_id)
        if scenario is None:
            raise ApplicationError(
                "SCENARIO_NOT_FOUND", "The requested simulation scenario was not found.", 404
            )
        return scenario


scenario_service = ScenarioService()
