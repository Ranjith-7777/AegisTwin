"""Start the local simulation-only API after migrating its disposable E2E database."""

import os
import sys
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("SIMULATION_ONLY", "true")
identity = str(os.getpid())
os.environ.setdefault("DATABASE_URL", f"sqlite:///./.e2e/aegistwin-e2e-{identity}.db")
os.environ.setdefault("MODEL_ARTIFACT_DIR", f".e2e/artifacts-{identity}")
os.environ.setdefault("CORS_ORIGINS", "http://127.0.0.1:4307")
(BACKEND / ".e2e" / f"artifacts-{identity}").mkdir(parents=True, exist_ok=True)

configuration = Config(str(BACKEND / "alembic.ini"))
command.upgrade(configuration, "head")
uvicorn.run("app.main:app", host="127.0.0.1", port=8010, log_level="warning")
