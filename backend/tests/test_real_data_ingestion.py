"""Recorded-dataset pipeline on CIC-IDS2017-layout *fixtures*: adapter,
validation, de-duplication, mapping, persistence, evaluation protocol,
correlation rules and the read-only API. No assertion here is a claim about
real CIC-IDS2017 performance - see tests/test_cicids2017_acceptance.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import NetworkFlowRecord
from app.ingestion.adapters import cicids2017
from app.ingestion.adapters.cicids2017 import UnsupportedLayout, parse_timestamp
from app.ingestion.asset_mapping import EXTERNAL_INTERNET, map_endpoint
from app.ingestion.canonical import SourceKind
from app.ingestion.importer import ImportRefused, import_file
from app.services.network_flow import features
from app.services.network_flow.correlation_service import correlate
from app.services.network_flow.evaluation_service import (
    EvaluationConfig,
    EvaluationRefused,
    binary_metrics,
    evaluate,
)
from tests.cicids_fixtures import CIC_HEADER, FixtureFlow, benign_day, row, ssh_patator, write_cic

MONDAY = "3/7/2017"
TUESDAY = "4/7/2017"


def _session(client: TestClient) -> Session:
    return cast(Session, cast(FastAPI, client.app).state.database.session_factory())


# ---------------------------------------------------------------- adapter


def test_timestamp_parsing_handles_missing_am_pm_and_seconds() -> None:
    morning, adjusted = parse_timestamp("4/7/2017 9:05")
    assert (morning.day, morning.month, morning.hour, adjusted) == (4, 7, 9, False)
    afternoon, adjusted = parse_timestamp("4/7/2017 1:05")
    assert (afternoon.hour, adjusted) == (13, True)
    with_seconds, _ = parse_timestamp("03/07/2017 08:55:58")
    assert (with_seconds.hour, with_seconds.second) == (8, 58)
    explicit, adjusted = parse_timestamp("7/7/2017 03:30:00 PM")
    assert (explicit.hour, adjusted) == (15, False)
    assert morning.utcoffset() is not None and morning.utcoffset().total_seconds() == -3 * 3600  # type: ignore[union-attr]


def test_machine_learning_layout_is_rejected_with_a_hint(tmp_path: Path) -> None:
    path = tmp_path / "ml.csv"
    path.write_text(" Destination Port, Flow Duration, Label\n80,10,BENIGN\n", encoding="latin-1")
    with pytest.raises(UnsupportedLayout, match="MachineLearningCVE"):
        list(cicids2017.read_rows(path))


def test_import_reports_every_row_and_never_invents_values(
    client: TestClient, tmp_path: Path
) -> None:
    good = FixtureFlow("192.168.10.5", 50000, "192.168.10.50", 80, f"{MONDAY} 9:00")
    infinite_rate = FixtureFlow(
        "192.168.10.9", 50001, "8.8.8.8", 53, f"{MONDAY} 9:01",
        duration_us="0", bytes_rate="Infinity", packets_rate="NaN", protocol="17",
    )  # fmt: skip
    unknown_host = FixtureFlow("192.168.10.200", 50002, "192.168.10.3", 389, f"{MONDAY} 2:15")
    bad_ip = row(FixtureFlow("999.1.1.1", 1, "192.168.10.3", 53, f"{MONDAY} 9:02"))
    negative = row(FixtureFlow("192.168.10.5", 2, "192.168.10.3", 53, f"{MONDAY} 9:03",
                               duration_us="-1"))  # fmt: skip
    bad_time = row(FixtureFlow("192.168.10.5", 3, "192.168.10.3", 53, "yesterday"))
    truncated = row(good)[:10]
    path = write_cic(
        tmp_path / "Monday.csv",
        [good, good, infinite_rate, unknown_host],
        [bad_ip, negative, bad_time, truncated],
    )

    session = _session(client)
    try:
        result = import_file(session, path, "cicids2017", "pytest")
        source = result.source
        assert result.created
        assert source.source_kind == SourceKind.REPLAY.value
        assert source.rows_read == 8
        assert (source.rows_accepted, source.rows_duplicate, source.rows_rejected) == (3, 1, 4)
        assert (
            source.rows_read == source.rows_accepted + source.rows_rejected + source.rows_duplicate
        )
        assert source.rejection_reasons_json == {
            "invalid_src_ip": 1,
            "invalid_timestamp": 1,
            "negative_duration": 1,
            "truncated_row": 1,
        }
        assert source.rows_unmapped == 1
        assert source.unmapped_endpoints_json == {"192.168.10.200": 1}
        assert source.rows_timestamp_adjusted == 1
        assert source.rows_rate_missing == 1
        assert source.label_counts_json == {"BENIGN": 3}
        assert any("UTC-03:00" in note for note in source.provenance_notes_json)

        stored = {flow.src_ip: flow for flow in session.scalars(select(NetworkFlowRecord)).all()}
        assert stored["192.168.10.9"].flow_bytes_per_s is None  # not invented
        assert stored["192.168.10.9"].dst_testbed_identity == EXTERNAL_INTERNET
        assert stored["192.168.10.5"].dst_asset_id == "api-gateway-01"
        assert stored["192.168.10.5"].src_asset_id is None  # workstation: identity only
        assert stored["192.168.10.5"].src_testbed_identity == "cic-win81"

        again = import_file(session, path, "cicids2017", "pytest")
        assert not again.created and again.source.source_id == source.source_id
        assert session.scalar(select(func.count()).select_from(NetworkFlowRecord)) == 3
    finally:
        session.close()


def test_import_refuses_non_replay_kinds_and_blank_provenance(
    client: TestClient, tmp_path: Path
) -> None:
    path = write_cic(tmp_path / "x.csv", benign_day(1, 3, MONDAY))
    session = _session(client)
    try:
        with pytest.raises(ImportRefused):
            import_file(session, path, "cicids2017", "pytest", SourceKind.LIVE_READONLY)
        with pytest.raises(ImportRefused):
            import_file(session, path, "canonical", "pytest")
    finally:
        session.close()


def test_canonical_json_adapter_requires_timezone(client: TestClient, tmp_path: Path) -> None:
    base = {
        "src_ip": "10.0.0.5", "src_port": 51000, "dst_ip": "10.0.0.9", "dst_port": 443,
        "protocol": 6, "duration_s": 0.5, "fwd_packets": 4, "bwd_packets": 3,
        "fwd_bytes": 400, "bwd_bytes": 900,
    }  # fmt: skip
    path = tmp_path / "flows.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({**base, "observed_at": "2026-03-01T10:00:00+00:00"}),
                json.dumps({**base, "observed_at": "2026-03-01T10:00:01"}),
                "{not json",
            ]
        ),
        encoding="utf-8",
    )
    session = _session(client)
    try:
        source = import_file(
            session, path, "canonical", "pytest", dataset_name="lab", licence="internal"
        ).source
        assert source.rows_accepted == 1
        assert source.rejection_reasons_json == {
            "invalid_json_record": 1,
            "timestamp_without_offset": 1,
        }
        assert source.label_counts_json == {}
    finally:
        session.close()


def test_endpoint_mapping_separates_identity_from_projection() -> None:
    assert map_endpoint("172.16.0.1").projected_asset_id == "external-user-01"
    assert map_endpoint("192.168.10.51").testbed_identity == "cic-ubuntu-server-12"
    workstation = map_endpoint("192.168.10.14")
    assert workstation.testbed_identity == "cic-win10-32" and workstation.projected_asset_id is None
    assert map_endpoint("10.9.9.9").testbed_identity is None


# ----------------------------------------------------------- features / leakage


def test_features_never_include_labels_identities_or_time() -> None:
    names = set(features.FEATURE_NAMES)
    for forbidden in features.FORBIDDEN_FEATURE_SOURCES:
        assert all(forbidden not in name for name in names)
    flow = NetworkFlowRecord(
        duration_s=0.0, fwd_packets=1, bwd_packets=0, fwd_bytes=0, bwd_bytes=0,
        syn_count=1, fin_count=0, rst_count=0, psh_count=0, ack_count=0,
        protocol=6, dst_port=22, evaluation_label="SSH-Patator", src_ip="1.2.3.4",
    )  # fmt: skip
    vector = features.flow_features(flow)
    flow.evaluation_label = "BENIGN"
    flow.src_ip = "5.6.7.8"
    assert features.flow_features(flow) == vector
    assert len(vector) == len(features.FEATURE_NAMES)
    assert all(np.isfinite(vector))


def test_binary_metrics_match_a_hand_computed_confusion_matrix() -> None:
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 0])
    scores = np.array([0.1, 0.2, 0.9, 0.3, 0.8, 0.95, 0.4, 0.05])
    metrics = binary_metrics(y_true, scores, threshold=0.5)
    assert metrics["confusion_matrix"] == {"tn": 4, "fp": 1, "fn": 1, "tp": 2}
    assert metrics["precision"] == pytest.approx(2 / 3)
    assert metrics["recall"] == pytest.approx(2 / 3)
    assert metrics["f1"] == pytest.approx(2 / 3)
    assert metrics["false_positive_rate"] == pytest.approx(1 / 5)
    # 13 of 15 benign/attack pairs are ranked correctly.
    assert metrics["roc_auc"] == pytest.approx(13 / 15)


# ------------------------------------------------------------- evaluation


def _import_days(client: TestClient, tmp_path: Path) -> tuple[Session, str, str]:
    monday = write_cic(tmp_path / "Monday.csv", benign_day(7, 400, MONDAY))
    tuesday = write_cic(
        tmp_path / "Tuesday.csv", benign_day(8, 200, TUESDAY) + ssh_patator(120, TUESDAY)
    )
    session = _session(client)
    train = import_file(session, monday, "cicids2017", "pytest").source.source_id
    test = import_file(session, tuesday, "cicids2017", "pytest").source.source_id
    return session, train, test


def test_evaluation_protocol_thresholds_on_benign_calibration_only(
    client: TestClient, tmp_path: Path
) -> None:
    session, train, test = _import_days(client, tmp_path)
    artifacts = tmp_path / "artifacts"
    try:
        record = evaluate(session, train, test, artifacts, EvaluationConfig(target_fpr=0.05))
        metrics = record.metrics_json
        assert metrics["train_rows_total"] == 400
        assert metrics["calibration_rows"] == 80 and metrics["train_rows_fit"] == 320
        assert metrics["eval_rows"] == 320
        assert metrics["support"] == {"benign": 200, "attack": 120}
        confusion = cast(dict[str, int], metrics["confusion_matrix"])
        assert sum(confusion.values()) == 320
        assert 0.0 <= cast(float, metrics["calibration_observed_fpr"]) <= 0.1
        per_label = cast(dict[str, dict[str, float]], metrics["per_label"])
        assert set(per_label) == {"BENIGN", "SSH-Patator"}
        assert per_label["SSH-Patator"]["flagged"] == confusion["tp"]
        assert str(record.protocol_json["labels_used_for"]).startswith("metrics only")
        assert (artifacts / "network-flow" / record.artifact_path).is_file()

        # Idempotent: same files + protocol -> same evaluation.
        again = evaluate(session, train, test, artifacts, EvaluationConfig(target_fpr=0.05))
        assert again.evaluation_id == record.evaluation_id
    finally:
        session.close()


def test_threshold_is_independent_of_evaluation_labels(client: TestClient, tmp_path: Path) -> None:
    session, train, test = _import_days(client, tmp_path)
    try:
        first = evaluate(session, train, test, tmp_path / "a", EvaluationConfig(target_fpr=0.02))
        for flow in session.scalars(
            select(NetworkFlowRecord).where(NetworkFlowRecord.source_id == test)
        ):
            flow.evaluation_label = "BENIGN" if flow.evaluation_label != "BENIGN" else "X-Attack"
        session.commit()
        session.delete(first)
        session.commit()
        second = evaluate(session, train, test, tmp_path / "b", EvaluationConfig(target_fpr=0.02))
        assert second.metrics_json["threshold"] == first.metrics_json["threshold"]
    finally:
        session.close()


def test_evaluation_refuses_leaky_or_invalid_protocols(client: TestClient, tmp_path: Path) -> None:
    session, train, test = _import_days(client, tmp_path)
    try:
        with pytest.raises(EvaluationRefused, match="different"):
            evaluate(session, train, train, tmp_path)
        with pytest.raises(EvaluationRefused, match="benign-only"):
            evaluate(session, test, train, tmp_path)
    finally:
        session.close()


# ------------------------------------------------------------ correlation


def test_rules_detect_brute_force_and_scans_from_flow_fields(
    client: TestClient, tmp_path: Path
) -> None:
    scan = [
        FixtureFlow("172.16.0.1", 41000, "192.168.10.51", port, f"{TUESDAY} 11:{port % 4:02d}",
                    fwd_packets="1", bwd_packets="1", fwd_bytes="0", bwd_bytes="0", syn="1",
                    rst="1", label="PortScan")
        for port in range(1, 80)
    ]  # fmt: skip
    path = write_cic(
        tmp_path / "Tuesday.csv", benign_day(3, 60, TUESDAY) + ssh_patator(60, TUESDAY) + scan
    )
    session = _session(client)
    try:
        source = import_file(session, path, "cicids2017", "pytest").source
        findings = correlate(session, source.source_id)
        rules = {finding.rule for finding in findings}
        assert {"brute_force", "port_scan"} <= rules
        brute = next(item for item in findings if item.rule == "brute_force")
        assert brute.mitre is not None and brute.mitre.technique_id == "T1110"
        assert brute.dst_asset_id == "api-gateway-01" and brute.src_asset_id == "external-user-01"
        assert brute.label_agreement == 1.0
        port_scan = next(item for item in findings if item.rule == "port_scan")
        assert port_scan.mitre is not None and port_scan.mitre.technique_id == "T1046"
        assert all(
            item.mitre is None for item in findings if item.rule in {"volume", "suspicious_remote"}
        )

        # Rules never read labels: relabelling everything changes nothing but agreement.
        for flow in session.scalars(select(NetworkFlowRecord)):
            flow.evaluation_label = "BENIGN"
        session.commit()
        relabelled = correlate(session, source.source_id)
        assert [(f.rule, f.src_ip, f.dst_ip, f.flow_count) for f in relabelled] == [
            (f.rule, f.src_ip, f.dst_ip, f.flow_count) for f in findings
        ]
        assert all(f.label_agreement == 0.0 for f in relabelled)
    finally:
        session.close()


# ----------------------------------------------------------------- API


def test_read_only_api_exposes_sources_findings_and_evaluation(
    client: TestClient, tmp_path: Path
) -> None:
    catalogue = client.get("/api/v1/data-sources").json()
    assert catalogue["imported"] == []
    assert catalogue["simulation_only"] is True
    kinds = {item["source_kind"]: item["status"] for item in catalogue["built_in"]}
    assert kinds == {"synthetic": "active", "live_readonly": "not_implemented"}
    assert client.get("/api/v1/data-sources/evaluations/latest").status_code == 404

    session, train, test = _import_days(client, tmp_path)
    try:
        evaluate(session, train, test, tmp_path)
    finally:
        session.close()

    imported = client.get("/api/v1/data-sources").json()["imported"]
    assert {item["file_name"] for item in imported} == {"Monday.csv", "Tuesday.csv"}
    assert all(item["source_kind"] == "replay" for item in imported)
    latest = client.get("/api/v1/data-sources/evaluations/latest").json()
    assert latest["eval_source_id"] == test
    detail = client.get(f"/api/v1/data-sources/{test}").json()
    assert detail["label_counts_json"] == {"BENIGN": 200, "SSH-Patator": 120}
    findings = client.get(f"/api/v1/data-sources/{test}/findings").json()
    assert findings["counts_by_rule"].get("brute_force", 0) >= 1
    assert client.get("/api/v1/data-sources/nope").status_code == 404
    assert client.post("/api/v1/data-sources").status_code == 405


def test_fixture_header_matches_real_layout() -> None:
    assert len(CIC_HEADER) == 85
    assert [name.strip() for name in CIC_HEADER].count("Fwd Header Length") == 2
