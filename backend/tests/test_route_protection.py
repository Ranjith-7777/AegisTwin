"""Every API operation requires an authenticated principal unless it is an
explicitly public health probe. Walks the live OpenAPI schema, so a newly
added route that forgets its role dependency fails here."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

PUBLIC = {
    ("GET", "/api/health"),
    ("GET", "/api/health/live"),
    ("GET", "/api/health/ready"),
}


def test_only_health_probes_are_reachable_without_authentication(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL=f"sqlite:///{(tmp_path / 'auth.db').as_posix()}",
        MODEL_ARTIFACT_DIR=tmp_path / "artifacts",
        ALLOW_ANONYMOUS_VIEWER=False,
    )
    with TestClient(create_app(settings)) as client:
        spec = client.get("/openapi.json").json()
        operations = [
            (method.upper(), path) for path, ops in spec["paths"].items() for method in ops
        ]
        assert len(operations) > 50
        assert ("GET", "/api/v1/data-sources") in operations
        assert ("GET", "/api/v1/workflow/runs/{run_id}/state") in operations

        unexpected = []
        for method, path in operations:
            status = client.request(method, re.sub(r"\{[^}]+\}", "x", path)).status_code
            expected = 200 if (method, path) in PUBLIC else 401
            if status != expected:
                unexpected.append((method, path, status))
        assert unexpected == []
