from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

from app.schemas.detection import DetectionTrainingRequest, SeedRange
from app.schemas.telemetry import TelemetryEvent
from app.services.event_generator import event_generator
from app.services.scenario_service import SCENARIOS

DATASET_NAMESPACE = UUID("16186d79-7d50-457d-aa6c-b16ffcc39765")


@dataclass(frozen=True)
class SyntheticDataset:
    events: list[TelemetryEvent]
    run_ids: tuple[str, ...]


@dataclass(frozen=True)
class TrainingDatasets:
    training: SyntheticDataset
    validation: SyntheticDataset
    fingerprint: str


class DetectionDatasetService:
    def __init__(self) -> None:
        self._scenarios = {scenario.scenario_id: scenario for scenario in SCENARIOS}

    def build_training(self, request: DetectionTrainingRequest) -> TrainingDatasets:
        training = self.build_scenario("normal-operations", request.training_seed_range, "train")
        validation = self.build_scenario(
            "normal-operations", request.validation_seed_range, "validation"
        )
        material = {
            "configuration": {
                "training_seed_range": request.training_seed_range.model_dump(),
                "validation_seed_range": request.validation_seed_range.model_dump(),
                "scenario_id": "normal-operations",
            },
            "training_runs": training.run_ids,
            "validation_runs": validation.run_ids,
            "events": [
                self._fingerprint_event(event) for event in training.events + validation.events
            ],
        }
        fingerprint = hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return TrainingDatasets(training=training, validation=validation, fingerprint=fingerprint)

    def build_scenario(
        self, scenario_id: str, seeds: SeedRange, split_name: str
    ) -> SyntheticDataset:
        scenario = self._scenarios[scenario_id]
        events: list[TelemetryEvent] = []
        run_ids: list[str] = []
        for seed in seeds.values():
            hour = 8 + seed % 9 if scenario_id == "normal-operations" else seed % 5
            start_time = datetime(2026, 1, 1, hour, tzinfo=UTC) + timedelta(days=seed % 28)
            run_id = str(
                uuid5(DATASET_NAMESPACE, f"{split_name}:{scenario_id}:{seed}:{start_time}")
            )
            run_ids.append(run_id)
            events.extend(event_generator.generate(scenario, run_id, seed, start_time))
        return SyntheticDataset(events=events, run_ids=tuple(run_ids))

    @staticmethod
    def _fingerprint_event(event: TelemetryEvent) -> dict[str, object]:
        data = event.model_dump(mode="json")
        for field in ("event_id", "simulation_run_id", "scenario_id", "created_at"):
            data.pop(field, None)
        return data


detection_dataset_service = DetectionDatasetService()
