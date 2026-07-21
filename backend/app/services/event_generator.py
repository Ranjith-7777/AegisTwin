from __future__ import annotations

from datetime import datetime, timedelta
from random import Random
from uuid import UUID, uuid5

from app.schemas.simulation import SimulationScenario
from app.schemas.telemetry import EventType, TelemetryEvent
from app.services.infrastructure_service import inventory_service

EVENT_NAMESPACE = UUID("3b0a8f60-cc97-4c4c-9044-1f0e35f38a1e")


class DeterministicEventGenerator:
    def generate(
        self,
        scenario: SimulationScenario,
        simulation_run_id: str,
        seed: int,
        start_time: datetime,
    ) -> list[TelemetryEvent]:
        random = Random(seed)
        events: list[TelemetryEvent] = []
        unseen_device_id = f"synthetic-unseen-device-{random.randint(100, 999)}"
        for step in scenario.steps:
            timestamp = start_time + timedelta(seconds=step.offset_seconds)
            source_id = step.source_id
            destination_id = step.destination_id
            device_id = (
                unseen_device_id if step.device_id == "synthetic-unseen-device" else step.device_id
            )
            failed_attempts = 0
            bytes_transferred = 0
            if scenario.scenario_id == "credential-compromise" and step.sequence == 1:
                failed_attempts = random.randint(5, 9)
            if step.event_type is EventType.DATA_TRANSFER:
                bytes_transferred = (
                    random.randint(180_000_000, 260_000_000)
                    if scenario.scenario_id == "credential-compromise"
                    else random.randint(18_000, 64_000)
                )
            destination_ip = (
                "203.0.113.200"
                if destination_id == "simulation-egress-sink-01"
                else inventory_service.get_ip(destination_id)
            )
            event_id = str(uuid5(EVENT_NAMESPACE, f"{simulation_run_id}:{step.sequence}"))
            events.append(
                TelemetryEvent(
                    event_id=event_id,
                    scenario_id=scenario.scenario_id,
                    simulation_run_id=simulation_run_id,
                    timestamp=timestamp,
                    event_type=step.event_type,
                    action=step.action,
                    outcome=step.outcome,
                    severity=step.severity,
                    source_type=step.source_type,
                    source_id=source_id,
                    destination_id=destination_id,
                    user_id=step.user_id,
                    device_id=device_id,
                    source_ip=inventory_service.get_ip(source_id),
                    destination_ip=destination_ip,
                    privilege_level=step.privilege_level,
                    failed_attempts=failed_attempts,
                    bytes_transferred=bytes_transferred,
                    process_name=step.process_name,
                    metadata={
                        **step.metadata,
                        "synthetic": True,
                        "scenario_step": step.sequence,
                        "description": step.description,
                    },
                    created_at=timestamp,
                )
            )
        return events


event_generator = DeterministicEventGenerator()
