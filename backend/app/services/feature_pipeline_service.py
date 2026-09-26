from __future__ import annotations

import math
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import TypeAlias

from app.schemas.telemetry import TelemetryEvent
from app.services.infrastructure_service import inventory_service

FEATURE_SCHEMA_VERSION = "synthetic-behaviour-v2"
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
    "seconds_since_previous_event",
    "rolling_failed_attempt_count",
    "cumulative_user_failed_attempts",
    "distinct_destinations_so_far",
    "distinct_user_sources_so_far",
    "user_device_binding_frequency",
    "user_source_binding_frequency",
    "source_destination_transition_frequency",
    "event_type_transition_frequency",
    "action_transition_frequency",
    "transfer_relative_to_user_baseline",
    "transfer_relative_to_event_type_baseline",
    "privilege_transition",
    "privilege_relative_to_user_baseline",
    "hour_relative_to_user_activity",
    "infrastructure_graph_distance",
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
    user_device_counts: dict[str, int]
    user_source_counts: dict[str, int]
    source_destination_counts: dict[str, int]
    event_transition_counts: dict[str, int]
    action_transition_counts: dict[str, int]
    event_count: int
    numeric_mean: dict[str, float]
    numeric_std: dict[str, float]
    bytes_p99: float
    categorical_counts: dict[str, dict[str, int]]
    user_transfer_mean: dict[str, float]
    event_transfer_mean: dict[str, float]
    user_hour_mean: dict[str, float]
    user_privilege_mode: dict[str, str]


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
        user_transfers: dict[str, list[float]] = defaultdict(list)
        event_transfers: dict[str, list[float]] = defaultdict(list)
        user_hours: dict[str, list[float]] = defaultdict(list)
        user_privileges: dict[str, Counter[str]] = defaultdict(Counter)
        user_device: Counter[str] = Counter()
        user_source: Counter[str] = Counter()
        source_destination: Counter[str] = Counter()
        event_transitions: Counter[str] = Counter()
        action_transitions: Counter[str] = Counter()
        previous_by_run: dict[str, TelemetryEvent] = {}
        for event in events:
            user = event.user_id or "missing"
            device = event.device_id or "missing"
            destination = event.destination_id or "missing"
            privilege = event.privilege_level.value if event.privilege_level else "missing"
            user_device[f"{user}|{device}"] += 1
            user_source[f"{user}|{event.source_id}"] += 1
            source_destination[f"{event.source_id}|{destination}"] += 1
            user_transfers[user].append(float(event.bytes_transferred))
            event_transfers[event.event_type.value].append(float(event.bytes_transferred))
            user_hours[user].append(float(event.timestamp.hour))
            user_privileges[user][privilege] += 1
            previous = previous_by_run.get(event.simulation_run_id)
            if previous:
                event_transitions[f"{previous.event_type.value}|{event.event_type.value}"] += 1
                action_transitions[f"{previous.action.value}|{event.action.value}"] += 1
            previous_by_run[event.simulation_run_id] = event
        sorted_bytes = sorted(float(event.bytes_transferred) for event in events)
        p99_index = min(len(sorted_bytes) - 1, math.ceil(0.99 * len(sorted_bytes)) - 1)
        return FeatureBaselines(
            source_counts=dict(Counter(event.source_id for event in events)),
            destination_counts=dict(Counter(event.destination_id or "missing" for event in events)),
            user_counts=dict(Counter(event.user_id or "missing" for event in events)),
            device_counts=dict(Counter(event.device_id or "missing" for event in events)),
            user_device_counts=dict(user_device),
            user_source_counts=dict(user_source),
            source_destination_counts=dict(source_destination),
            event_transition_counts=dict(event_transitions),
            action_transition_counts=dict(action_transitions),
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
            user_transfer_mean={key: mean(values) for key, values in user_transfers.items()},
            event_transfer_mean={key: mean(values) for key, values in event_transfers.items()},
            user_hour_mean={key: mean(values) for key, values in user_hours.items()},
            user_privilege_mode={
                key: counts.most_common(1)[0][0] for key, counts in user_privileges.items()
            },
        )

    def extract(
        self, events: list[TelemetryEvent], baselines: FeatureBaselines
    ) -> list[FeatureRow]:
        assets = {asset.asset_id: asset for asset in inventory_service.list_assets()}
        state_by_run: dict[str, dict[str, object]] = {}
        rows: list[FeatureRow] = []
        denominator = max(1, baselines.event_count)
        for event in events:
            state = state_by_run.setdefault(
                event.simulation_run_id,
                {
                    "previous": None,
                    "devices": set(),
                    "failed_window": deque(maxlen=3),
                    "user_failed": Counter(),
                    "destinations": set(),
                    "user_sources": defaultdict(set),
                    "user_privilege": {},
                },
            )
            previous = state["previous"]
            devices = state["devices"]
            failed_window = state["failed_window"]
            user_failed = state["user_failed"]
            destinations = state["destinations"]
            user_sources = state["user_sources"]
            user_privilege = state["user_privilege"]
            assert isinstance(devices, set)
            assert isinstance(failed_window, deque)
            assert isinstance(user_failed, Counter)
            assert isinstance(destinations, set)
            assert isinstance(user_sources, defaultdict)
            assert isinstance(user_privilege, dict)
            user = event.user_id or "missing"
            device = event.device_id or "missing"
            destination = event.destination_id or "missing"
            privilege = event.privilege_level.value if event.privilege_level else "missing"
            unseen = device != "missing" and device not in devices
            devices.add(device)
            failed_window.append(event.failed_attempts)
            user_failed[user] += event.failed_attempts
            destinations.add(destination)
            user_sources[user].add(event.source_id)
            previous_privilege = user_privilege.get(user)
            privilege_transition = (
                previous_privilege is not None and previous_privilege != privilege
            )
            user_privilege[user] = privilege
            expected = bool(
                assets.get(event.source_id)
                and event.destination_id in assets[event.source_id].relationships
            )
            angle = 2 * math.pi * event.timestamp.hour / 24
            event_transition = (
                f"{previous.event_type.value}|{event.event_type.value}"
                if isinstance(previous, TelemetryEvent)
                else "start"
            )
            action_transition = (
                f"{previous.action.value}|{event.action.value}"
                if isinstance(previous, TelemetryEvent)
                else "start"
            )
            seconds_since_previous = (
                max(0.0, (event.timestamp - previous.timestamp).total_seconds())
                if isinstance(previous, TelemetryEvent)
                else 0.0
            )
            user_transfer = baselines.user_transfer_mean.get(user, 0.0)
            event_transfer = baselines.event_transfer_mean.get(event.event_type.value, 0.0)
            learned_hour = baselines.user_hour_mean.get(user, 12.0)
            hour_distance = min(
                abs(event.timestamp.hour - learned_hour),
                24 - abs(event.timestamp.hour - learned_hour),
            )
            rows.append(
                {
                    "hour_sin": math.sin(angle),
                    "hour_cos": math.cos(angle),
                    "failed_attempts": float(event.failed_attempts),
                    "log1p_bytes_transferred": math.log1p(event.bytes_transferred),
                    "privilege_level": privilege,
                    "source_asset_type": assets[event.source_id].asset_type.value
                    if event.source_id in assets
                    else "unknown",
                    "destination_asset_type": assets[destination].asset_type.value
                    if destination in assets
                    else "unknown",
                    "event_type": event.event_type.value,
                    "action": event.action.value,
                    "outcome": event.outcome.value,
                    "source_frequency": baselines.source_counts.get(event.source_id, 0)
                    / denominator,
                    "destination_frequency": baselines.destination_counts.get(destination, 0)
                    / denominator,
                    "user_frequency": baselines.user_counts.get(user, 0) / denominator,
                    "device_frequency": baselines.device_counts.get(device, 0) / denominator,
                    "device_unseen_within_run": unseen,
                    "expected_infrastructure_relationship": expected,
                    "seconds_since_previous_event": seconds_since_previous,
                    "rolling_failed_attempt_count": float(sum(failed_window)),
                    "cumulative_user_failed_attempts": float(user_failed[user]),
                    "distinct_destinations_so_far": float(len(destinations)),
                    "distinct_user_sources_so_far": float(len(user_sources[user])),
                    "user_device_binding_frequency": baselines.user_device_counts.get(
                        f"{user}|{device}", 0
                    )
                    / denominator,
                    "user_source_binding_frequency": baselines.user_source_counts.get(
                        f"{user}|{event.source_id}", 0
                    )
                    / denominator,
                    "source_destination_transition_frequency": (
                        baselines.source_destination_counts.get(
                            f"{event.source_id}|{destination}", 0
                        )
                        / denominator
                    ),
                    "event_type_transition_frequency": baselines.event_transition_counts.get(
                        event_transition, 0
                    )
                    / denominator,
                    "action_transition_frequency": baselines.action_transition_counts.get(
                        action_transition, 0
                    )
                    / denominator,
                    "transfer_relative_to_user_baseline": event.bytes_transferred
                    / max(1.0, user_transfer),
                    "transfer_relative_to_event_type_baseline": event.bytes_transferred
                    / max(1.0, event_transfer),
                    "privilege_transition": privilege_transition,
                    "privilege_relative_to_user_baseline": privilege
                    != baselines.user_privilege_mode.get(user, "missing"),
                    "hour_relative_to_user_activity": hour_distance / 12,
                    "infrastructure_graph_distance": float(
                        self._graph_distance(event.source_id, event.destination_id)
                    ),
                }
            )
            state["previous"] = event
        return rows

    def hybrid_components(
        self, event: TelemetryEvent, row: FeatureRow, baselines: FeatureBaselines
    ) -> dict[str, float]:
        numerical = max(
            min(1.0, event.failed_attempts / 5),
            min(1.0, float(row["transfer_relative_to_event_type_baseline"]) / 10),
            min(1.0, float(row["cumulative_user_failed_attempts"]) / 5),
            min(1.0, float(row["hour_relative_to_user_activity"]) * 2),
        )
        rarity_values = [
            float(row["device_frequency"]),
            float(row["user_device_binding_frequency"]),
            float(row["user_source_binding_frequency"]),
        ]
        categorical = max(
            1.0 - min(1.0, min(rarity_values) * baselines.event_count),
            float(bool(row["privilege_relative_to_user_baseline"])),
            float(bool(row["privilege_transition"])),
        )
        transition = 1.0 - min(
            1.0,
            max(
                float(row["event_type_transition_frequency"]),
                float(row["action_transition_frequency"]),
            )
            * baselines.event_count,
        )
        infrastructure = 0.0 if bool(row["expected_infrastructure_relationship"]) else 1.0
        return {
            "robust_numerical_deviation": numerical,
            "categorical_rarity": categorical,
            "behavioural_transition_rarity": transition,
            "infrastructure_novelty": infrastructure,
        }

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
        if float(row["hour_relative_to_user_activity"]) > 0.5:
            signals.append("Event hour differs from the learned synthetic user activity window.")
        if not bool(row["expected_infrastructure_relationship"]):
            signals.append(
                "Source-to-destination relationship is absent from the synthetic inventory."
            )
        if bool(row["privilege_transition"]):
            signals.append("Privilege level changed within the synthetic user sequence.")
        if float(row["event_type_transition_frequency"]) == 0:
            signals.append("Event transition was unseen in synthetic normal training data.")
        return signals[:4] or [
            "Combined feature pattern differs from the learned synthetic normal baseline."
        ]

    @staticmethod
    def _graph_distance(source_id: str, destination_id: str | None) -> int:
        if destination_id is None:
            return -1
        assets = {asset.asset_id: asset for asset in inventory_service.list_assets()}
        if source_id not in assets or destination_id not in assets:
            return -1
        graph: dict[str, set[str]] = defaultdict(set)
        for asset in assets.values():
            for related in asset.relationships:
                graph[asset.asset_id].add(related)
                graph[related].add(asset.asset_id)
        queue = deque([(source_id, 0)])
        visited = {source_id}
        while queue:
            current, distance = queue.popleft()
            if current == destination_id:
                return distance
            for neighbour in sorted(graph[current] - visited):
                visited.add(neighbour)
                queue.append((neighbour, distance + 1))
        return -1


feature_pipeline_service = FeaturePipelineService()
