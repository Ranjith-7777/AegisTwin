from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import TypeAlias

from app.schemas.telemetry import TelemetryEvent
from app.services.infrastructure_service import inventory_service

FEATURE_SCHEMA_VERSION = "synthetic-behaviour-v1"
FeatureValue: TypeAlias = str | float | bool
FeatureRow: TypeAlias = dict[str, FeatureValue]

INCLUDED_FEATURES = (
    "hour_sin",
    "hour_cos",
    "failed_attempts",
    "log1p_bytes_transferred",
    "privilege_level",
    "source_asset_type",
    "destination_asset_type",
    "event_type",
    "action",
    "outcome",
    "source_frequency",
    "destination_frequency",
    "user_frequency",
    "device_frequency",
    "device_unseen_within_run",
    "expected_infrastructure_relationship",
)

EXCLUDED_LEAKAGE_FIELDS = (
    "scenario_id",
    "simulation_run_id",
    "event_id",
    "synthetic",
    "scenario_name",
    "known_attack_label",
    "confirmed_attack_verdict",
    "evaluation_label",
    "database_primary_key",
    "severity",
    "model_generated_fields",
    "mitre_mapping",
    "incident_id",
)


@dataclass(frozen=True)
class FeatureBaselines:
    source_counts: dict[str, int]
    destination_counts: dict[str, int]
    user_counts: dict[str, int]
    device_counts: dict[str, int]
    event_count: int
    numeric_mean: dict[str, float]
    numeric_std: dict[str, float]
    bytes_p99: float
    categorical_counts: dict[str, dict[str, int]]


class FeaturePipelineService:
    def learn_baselines(self, events: list[TelemetryEvent]) -> FeatureBaselines:
        failed = [float(event.failed_attempts) for event in events]
        log_bytes = [math.log1p(event.bytes_transferred) for event in events]
        categorical = {
            "event_type": Counter(event.event_type.value for event in events),
            "action": Counter(event.action.value for event in events),
            "outcome": Counter(event.outcome.value for event in events),
            "privilege_level": Counter(
                event.privilege_level.value if event.privilege_level else "missing"
                for event in events
            ),
        }
        sorted_bytes = sorted(float(event.bytes_transferred) for event in events)
        p99_index = min(len(sorted_bytes) - 1, math.ceil(0.99 * len(sorted_bytes)) - 1)
        return FeatureBaselines(
            source_counts=dict(Counter(event.source_id for event in events)),
            destination_counts=dict(Counter(event.destination_id or "missing" for event in events)),
            user_counts=dict(Counter(event.user_id or "missing" for event in events)),
            device_counts=dict(Counter(event.device_id or "missing" for event in events)),
            event_count=len(events),
            numeric_mean={
                "failed_attempts": mean(failed),
                "log1p_bytes_transferred": mean(log_bytes),
            },
            numeric_std={
                "failed_attempts": pstdev(failed) or 1.0,
                "log1p_bytes_transferred": pstdev(log_bytes) or 1.0,
            },
            bytes_p99=sorted_bytes[p99_index],
            categorical_counts={name: dict(counts) for name, counts in categorical.items()},
        )

    def extract(
        self, events: list[TelemetryEvent], baselines: FeatureBaselines
    ) -> list[FeatureRow]:
        assets = {asset.asset_id: asset for asset in inventory_service.list_assets()}
        seen_by_run: dict[str, set[str]] = {}
        rows: list[FeatureRow] = []
        denominator = max(1, baselines.event_count)
        for event in events:
            run_seen = seen_by_run.setdefault(event.simulation_run_id, set())
            device = event.device_id or "missing"
            unseen = device != "missing" and device not in run_seen
            run_seen.add(device)
            source = assets.get(event.source_id)
            destination = assets.get(event.destination_id or "")
            expected = bool(source and event.destination_id in source.relationships)
            angle = 2 * math.pi * event.timestamp.hour / 24
            rows.append(
                {
                    "hour_sin": math.sin(angle),
                    "hour_cos": math.cos(angle),
                    "failed_attempts": float(event.failed_attempts),
                    "log1p_bytes_transferred": math.log1p(event.bytes_transferred),
                    "privilege_level": event.privilege_level.value
                    if event.privilege_level
                    else "missing",
                    "source_asset_type": source.asset_type.value if source else "unknown",
                    "destination_asset_type": destination.asset_type.value
                    if destination
                    else "unknown",
                    "event_type": event.event_type.value,
                    "action": event.action.value,
                    "outcome": event.outcome.value,
                    "source_frequency": baselines.source_counts.get(event.source_id, 0)
                    / denominator,
                    "destination_frequency": baselines.destination_counts.get(
                        event.destination_id or "missing", 0
                    )
                    / denominator,
                    "user_frequency": baselines.user_counts.get(event.user_id or "missing", 0)
                    / denominator,
                    "device_frequency": baselines.device_counts.get(device, 0) / denominator,
                    "device_unseen_within_run": unseen,
                    "expected_infrastructure_relationship": expected,
                }
            )
        return rows

    def contributing_signals(
        self, event: TelemetryEvent, row: FeatureRow, baselines: FeatureBaselines
    ) -> list[str]:
        signals: list[str] = []
        if (
            event.failed_attempts
            > baselines.numeric_mean["failed_attempts"]
            + 3 * baselines.numeric_std["failed_attempts"]
        ):
            signals.append("Failed-attempt count is above the learned synthetic normal range.")
        if event.bytes_transferred > baselines.bytes_p99:
            signals.append("Transfer volume exceeds the learned synthetic normal 99th percentile.")
        if (
            bool(row["device_unseen_within_run"])
            and baselines.device_counts.get(event.device_id or "missing", 0) == 0
        ):
            signals.append(
                "Device identifier was unseen in training and earlier in this synthetic run."
            )
        if event.timestamp.hour < 7 or event.timestamp.hour > 19:
            signals.append("Event occurred outside learned synthetic office-hour expectations.")
        if not bool(row["expected_infrastructure_relationship"]):
            signals.append(
                "Source-to-destination relationship is absent from the synthetic inventory."
            )
        for name, value in (
            ("event type", event.event_type.value),
            ("outcome", event.outcome.value),
            (
                "privilege level",
                event.privilege_level.value if event.privilege_level else "missing",
            ),
        ):
            counts = baselines.categorical_counts[name.replace(" ", "_")]
            if counts.get(value, 0) == 0:
                signals.append(
                    f"{name.capitalize()} is rare or unseen in synthetic normal training data."
                )
        return signals[:4] or [
            "Combined feature pattern differs from the learned synthetic normal baseline."
        ]


feature_pipeline_service = FeaturePipelineService()
