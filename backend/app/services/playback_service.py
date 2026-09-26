from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.playback import PlaybackMetadata
from app.services.simulation_service import simulation_run_service
from app.services.telemetry_service import telemetry_service


class PlaybackService:
    def get_metadata(self, session: Session, run_id: str) -> PlaybackMetadata:
        run = simulation_run_service.get_run(session, run_id)
        events = telemetry_service.list_run_events(session, run_id)
        first_timestamp = events[0].timestamp if events else None
        last_timestamp = events[-1].timestamp if events else None
        duration = (
            (last_timestamp - first_timestamp).total_seconds()
            if first_timestamp is not None and last_timestamp is not None
            else 0.0
        )
        return PlaybackMetadata(
            run=run,
            total_events=len(events),
            first_event_timestamp=first_timestamp,
            last_event_timestamp=last_timestamp,
            simulated_duration_seconds=duration,
            default_playback_speed=run.playback_speed,
        )


playback_service = PlaybackService()
