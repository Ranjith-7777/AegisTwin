"""End-to-end Phase 3 demonstration: healthy twin -> attack graph -> blast
radius -> a defense-enabled Purple Team experiment, all against a
deterministic synthetic backend. Prints each stage's real result so the
sequence can be read and verified, not just "ran without error."
"""

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
    database = (BACKEND / "aegistwin-phase3-demo.db").resolve()
    artifacts = (BACKEND / "artifacts" / "phase3-demo-models").resolve()
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
        print("== 1. Healthy twin ==")
        topology = client.get("/api/v1/topology").json()
        print(f"{len(topology['nodes'])} synthetic assets, {len(topology['edges'])} relationships")

        print("\n== 2. Attack Graph: top potential path to a critical asset ==")
        paths = client.get(
            "/api/v1/attack-graph/paths",
            params={"source_asset_id": "external-user-01", "path_type": "potential", "max_paths": 1},
        ).json()
        top_path = paths["paths"][0]
        print(top_path["statement"])
        print(f"Priority score: {top_path['score']['total']}/100")

        print("\n== 3. Blast Radius: if auth-pod-01 is compromised ==")
        blast = client.post(
            "/api/v1/blast-radius", json={"compromised_asset_ids": ["auth-pod-01"]}
        ).json()
        print(blast["statement"])

        print("\n== 4. Purple Team: defense-enabled leaked-api-credential experiment ==")
        experiment = client.post(
            "/api/v1/purple-team/experiments",
            json={
                "scenario_id": "leaked-api-credential",
                "mode": "defense_enabled",
                "seed": 84,
                "top_k": 3,
            },
        ).json()
        summary = experiment["summary"]
        print(f"Status: {experiment['status']}")
        print(
            f"Detected {summary['detected_steps']}/{summary['total_steps']} steps "
            f"({summary['detection_step_coverage']:.0%} coverage of expected-detectable steps)"
        )
        print(f"Incident created: {summary['incident_created']}")
        print(f"Response executed: {summary['response_executed']}")
        print(f"Final outcome: {summary['final_outcome']}")

    print("\nAll data and actions remain synthetic. No production system was touched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
