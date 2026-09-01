from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="AegisArena API", validation_alias="APP_NAME")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    debug: bool = Field(default=False, validation_alias="DEBUG")
    api_prefix: str = Field(default="/api", validation_alias="API_PREFIX")
    backend_host: str = Field(default="127.0.0.1", validation_alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, ge=1, le=65535, validation_alias="BACKEND_PORT")
    database_url: str = Field(default="sqlite:///./aegistwin.db", validation_alias="DATABASE_URL")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"], validation_alias="CORS_ORIGINS"
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    simulation_only: bool = Field(default=True, validation_alias="SIMULATION_ONLY")
    demo_mode: bool = Field(default=False, validation_alias="DEMO_MODE")
    build_mode: str = Field(default="development", validation_alias="AEGISTWIN_BUILD_MODE")
    git_commit: str | None = Field(default=None, validation_alias="AEGISTWIN_GIT_COMMIT")
    benchmark_report_timestamp: str | None = Field(
        default=None, validation_alias="AEGISTWIN_BENCHMARK_TIMESTAMP"
    )
    model_artifact_dir: Path = Field(
        default=Path("artifacts/models"), validation_alias="MODEL_ARTIFACT_DIR"
    )

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        normalised = value.rstrip("/")
        if not normalised.startswith("/") or normalised == "":
            raise ValueError("API_PREFIX must be a non-root path beginning with '/'")
        return normalised

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        candidate = value.strip()
        if candidate.startswith("["):
            parsed = json.loads(candidate)
            if not isinstance(parsed, list):
                raise ValueError("CORS_ORIGINS JSON must be an array")
            return parsed
        return [origin.strip() for origin in candidate.split(",") if origin.strip()]

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: list[str]) -> list[str]:
        if any(origin == "*" for origin in value):
            raise ValueError("Wildcard CORS origins are not allowed")
        if any(not origin.startswith(("http://", "https://")) for origin in value):
            raise ValueError("Each CORS origin must use http:// or https://")
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalised = value.upper()
        if normalised not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("LOG_LEVEL is not supported")
        return normalised

    @field_validator("git_commit")
    @classmethod
    def validate_git_commit(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if (
            not all(character in "0123456789abcdefABCDEF" for character in value)
            or not 7 <= len(value) <= 40
        ):
            raise ValueError("AEGISTWIN_GIT_COMMIT must be a 7-40 character hexadecimal revision")
        return value.lower()


@lru_cache
def get_settings() -> Settings:
    return Settings()
