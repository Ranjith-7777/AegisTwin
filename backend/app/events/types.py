"""Canonical domain event type names.

Names follow the ``<domain>.<action>`` convention agreed for Phase 1. Only
event types that are actually published somewhere in this codebase are
marked ``# published``; the remainder are reserved so future phases can use
a stable, already-agreed vocabulary without inventing new names ad hoc.
Reserving a name here does NOT mean the underlying feature is implemented.
"""

from __future__ import annotations

from enum import StrEnum


class EventType(StrEnum):
    SCENARIO_STARTED = "scenario.started"  # published
    SCENARIO_COMPLETED = "scenario.completed"

    ATTACK_STARTED = "attack.started"
    ATTACK_STEP_EXECUTED = "attack.step.executed"

    TELEMETRY_GENERATED = "telemetry.generated"  # published
    TELEMETRY_RECEIVED = "telemetry.received"

    ANOMALY_DETECTED = "anomaly.detected"  # published

    INCIDENT_CREATED = "incident.created"  # published
    INCIDENT_UPDATED = "incident.updated"
    INCIDENT_CONTAINED = "incident.contained"

    MITRE_OBSERVATION_CREATED = "mitre.observation.created"

    PREDICTION_GENERATED = "prediction.generated"  # published

    RESPONSE_PROPOSED = "response.proposed"  # published
    RESPONSE_APPROVED = "response.approved"  # published
    RESPONSE_REJECTED = "response.rejected"  # published
    RESPONSE_EXECUTION_STARTED = "response.execution.started"  # published
    RESPONSE_EXECUTED = "response.executed"  # published
    RESPONSE_FAILED = "response.failed"  # published

    RESOURCE_STATE_CHANGED = "resource.state.changed"  # published

    VERIFICATION_COMPLETED = "verification.completed"  # published

    ROLLBACK_STARTED = "rollback.started"  # published
    ROLLBACK_COMPLETED = "rollback.completed"  # published
