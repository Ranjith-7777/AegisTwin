"""Create exactly one compatible deterministic model in an isolated demo database."""

import argparse
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--artifacts", required=True)
    args = parser.parse_args()
    database = Path(args.database).resolve()
    artifacts = Path(args.artifacts).resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        DATABASE_URL=f"sqlite:///{database.as_posix()}",
        MODEL_ARTIFACT_DIR=str(artifacts),
        SIMULATION_ONLY="true",
        ENVIRONMENT="demo",
        DEMO_MODE="true",
    )
    os.chdir(BACKEND)
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")

    from app.core.config import Settings
    from app.main import create_app

    with TestClient(create_app(Settings())) as client:
        models = client.get("/api/v1/detection/models").json()
        compatible = next(
            (
                model
                for model in models
                if model["random_state"] == 17
                and model["feature_schema_version"] == "synthetic-behaviour-v2"
                and Path(model["artifact_path"]).is_file()
            ),
            None,
        )
        if compatible is None:
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
            compatible = response.json()
            disposition = "created"
        else:
            disposition = "reused"
    print(f"MODEL_ID={compatible['model_id']}")
    print(f"MODEL_STATUS={disposition}")
    print("MODEL_SEED=84")
    print("SYNTHETIC_ONLY=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
