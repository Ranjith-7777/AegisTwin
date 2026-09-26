"""Prepare deterministic local AegisArena demonstration state without real integrations."""

import argparse
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap synthetic AegisArena demo state.")
    parser.add_argument("--database", default=str(BACKEND / "aegistwin-demo.db"))
    parser.add_argument("--artifacts", default=str(BACKEND / "artifacts" / "demo-models"))
    args = parser.parse_args()
    database = Path(args.database).resolve()
    artifacts = Path(args.artifacts).resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    os.environ["SIMULATION_ONLY"] = "true"
    os.environ["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    os.environ["MODEL_ARTIFACT_DIR"] = str(artifacts)
    os.chdir(BACKEND)
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")

    from app.core.config import Settings
    from app.main import create_app

    settings = Settings(
        DATABASE_URL=os.environ["DATABASE_URL"],
        MODEL_ARTIFACT_DIR=artifacts,
        SIMULATION_ONLY=True,
        DEBUG=False,
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/detection/models/train",
            json={
                "training_seed_range": {"start": 1, "end": 5},
                "validation_seed_range": {"start": 6, "end": 10},
                "evaluation_seed_range": {"start": 11, "end": 13},
                "random_state": 17,
                "target_false_positive_rate": 0.1,
                "n_estimators": 100,
            },
        )
        response.raise_for_status()
        model_id = response.json()["model_id"]
    print("AegisArena synthetic demo bootstrap complete.")
    print(f"Deterministic model: {model_id}")
    print("Backend: cd backend && python -m uvicorn app.main:app --reload")
    print("Frontend: cd frontend && npm run dev")
    print("Scenario: staged-compromise-demo; seed: 84; playback speed: 50")
    print("All data and actions remain synthetic. Human approval gates remain enabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
