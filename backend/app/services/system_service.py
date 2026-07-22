from app.core.config import Settings, get_settings
from app.core.constants import SYSTEM_NAME
from app.schemas.system import SystemStatusResponse


def get_system_status(settings: Settings | None = None) -> SystemStatusResponse:
    active_settings = settings or get_settings()
    return SystemStatusResponse(
        system_name=SYSTEM_NAME,
        mode="simulation",
        operational=True,
        active_incidents=0,
        agents_online=0,
        version="0.8.0",
        git_commit=active_settings.git_commit,
        build_mode=active_settings.build_mode,
        demo_mode=active_settings.demo_mode,
        database_revision="20260722_0008",
        synthetic_only=active_settings.simulation_only,
        benchmark_report_timestamp=active_settings.benchmark_report_timestamp,
    )
