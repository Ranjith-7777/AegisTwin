from pydantic import BaseModel


class SafetyResponse(BaseModel):
    simulation_only: bool
    real_world_actions_enabled: bool
    external_targets_allowed: bool
    message: str
