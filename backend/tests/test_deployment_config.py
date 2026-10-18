"""Static regression checks on the deployment configuration (no Docker needed).

Each assertion pins a previously real defect: the dev compose mapped the
frontend to a port nginx does not listen on, nginx dropped the WebSocket
upgrade for /api/v1/ws/, model artifacts were not persisted, and the non-root
backend could not write a freshly created /data volume.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_dev_compose_maps_host_port_to_the_nginx_listen_port() -> None:
    compose = _read("docker-compose.yml")
    nginx = _read("frontend/nginx.conf.template")
    listen = re.search(r"listen\s+(\d+);", nginx)
    assert listen is not None
    assert f'"5173:{listen.group(1)}"' in compose


def test_nginx_upgrades_the_playback_websocket_path() -> None:
    nginx = _read("frontend/nginx.conf.template")
    block = nginx.split("location /api/v1/ws/", 1)[1].split("\n    }", 1)[0]
    assert "proxy_set_header Upgrade $http_upgrade;" in block
    assert 'proxy_set_header Connection "upgrade";' in block
    # It must be declared before the generic /api/ prefix block.
    assert nginx.index("location /api/v1/ws/") < nginx.index("location /api/ {")


def test_model_artifacts_are_persisted_with_the_database() -> None:
    for compose_file in ("docker-compose.yml", "docker-compose.prod.yml"):
        compose = _read(compose_file)
        assert "MODEL_ARTIFACT_DIR: /data/models" in compose, compose_file
        assert re.search(r"- [\w-]+:/data\b", compose), compose_file


def test_backend_image_prepares_a_writable_data_directory_for_the_non_root_user() -> None:
    dockerfile = _read("backend/Dockerfile")
    assert "mkdir -p /data/models" in dockerfile
    chown = dockerfile.index("chown -R aegis:aegis")
    assert "/data" in dockerfile[chown : dockerfile.index("\n", chown)]
    assert dockerfile.index("chown -R aegis:aegis") < dockerfile.index("USER aegis")


def test_production_compose_never_enables_the_development_bypass() -> None:
    compose = _read("docker-compose.prod.yml")
    assert "AUTH_DEV_BYPASS_ROLE" not in compose
    assert "ENVIRONMENT: production" in compose
