"""Persisted, singleton Blue Agent autonomy configuration. See
docs/architecture/AUTONOMY_MODEL.md."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import AutonomyConfigRecord
from app.events.envelope import AutonomyDecisionPayload, DomainEvent
from app.events.registry import get_event_bus
from app.events.types import EventType
from app.schemas.autonomy import AUTONOMY_DESCRIPTIONS, AutonomyConfig, AutonomyMode

SINGLETON_ID = "singleton"
DEFAULT_MODE = AutonomyMode.RECOMMEND


class AutonomyService:
    def get(self, session: Session) -> AutonomyConfig:
        record = session.get(AutonomyConfigRecord, SINGLETON_ID)
        if record is None:
            now = datetime.now(UTC)
            record = AutonomyConfigRecord(
                id=SINGLETON_ID,
                mode=DEFAULT_MODE.value,
                updated_by="system-default",
                updated_at=now,
                synthetic=True,
            )
            session.add(record)
            session.flush()
        return self._schema(record)

    def set_mode(self, session: Session, mode: AutonomyMode, updated_by: str) -> AutonomyConfig:
        record = session.get(AutonomyConfigRecord, SINGLETON_ID)
        previous_mode = record.mode if record is not None else DEFAULT_MODE.value
        if record is None:
            record = AutonomyConfigRecord(id=SINGLETON_ID, mode=mode.value, updated_by=updated_by)
            session.add(record)
        else:
            record.mode = mode.value
            record.updated_by = updated_by
        record.updated_at = datetime.now(UTC)
        session.flush()
        get_event_bus().publish(
            DomainEvent(
                event_type=EventType.AUTONOMY_DECISION,
                source="autonomy",
                correlation_id=SINGLETON_ID,
                payload=AutonomyDecisionPayload(
                    autonomy_mode=mode.value,
                    recommendation_id="n/a",
                    decision=f"mode_changed:{previous_mode}->{mode.value}",
                    reason=f"Autonomy mode explicitly changed by {updated_by}.",
                ),
            )
        )
        session.commit()
        return self._schema(record)

    def require_mode(self, session: Session) -> AutonomyMode:
        return self.get(session).mode

    def _schema(self, record: AutonomyConfigRecord) -> AutonomyConfig:
        try:
            mode = AutonomyMode(record.mode)
        except ValueError as exc:
            raise ApplicationError(
                "AUTONOMY_MODE_CORRUPT", f"Unknown persisted autonomy mode '{record.mode}'.", 500
            ) from exc
        return AutonomyConfig(
            mode=mode,
            description=AUTONOMY_DESCRIPTIONS[mode],
            updated_by=record.updated_by,
            updated_at=record.updated_at,
        )


autonomy_service = AutonomyService()
