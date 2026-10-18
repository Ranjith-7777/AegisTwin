"""Correlation rules over recorded network flows (`network-flow-rules-v1`).

Rules read flow fields only (endpoints, ports, counts, bytes, time) and
never `evaluation_label`. After a finding is formed, the labels of its own
flows are summarised as `label_agreement` - an *evaluation* of the rule
against ground truth, shown next to the finding, never an input to it.

MITRE ATT&CK mapping is attached only where flow evidence alone supports
the technique:

* brute_force -> T1110 Brute Force (parent technique): many short
  connections from one source to one authentication service. Flow data
  cannot show authentication outcomes or distinguish guessing from
  spraying, so no sub-technique is claimed.
* port_scan -> T1046 Network Service Discovery: one source probing many
  distinct destination ports on one host.
* volume and suspicious_remote: no technique - large transfers and
  non-standard-port traffic have many benign explanations, so the finding
  stays an unmapped observation.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import NetworkFlowRecord
from app.ingestion.asset_mapping import EXTERNAL_INTERNET
from app.ingestion.canonical import BENIGN_LABEL

RULESET_VERSION = "network-flow-rules-v1"

AUTH_PORTS = {21: "FTP", 22: "SSH", 23: "Telnet", 3389: "RDP", 445: "SMB", 5900: "VNC"}
COMMON_PORTS = frozenset(
    {
        20,
        21,
        22,
        25,
        53,
        80,
        88,
        110,
        123,
        137,
        138,
        139,
        143,
        389,
        443,
        445,
        465,
        587,
        636,
        993,
        995,
        3268,
        3389,
        8080,
        8443,
    }
)


@dataclass(frozen=True)
class RuleThresholds:
    window_minutes: int = 5
    brute_force_min_flows: int = 30
    port_scan_min_ports: int = 50
    volume_min_bytes: int = 10_000_000
    remote_min_flows: int = 20


@dataclass(frozen=True)
class Mitre:
    technique_id: str
    name: str
    rationale: str


MITRE_BRUTE_FORCE = Mitre(
    "T1110",
    "Brute Force",
    "Repeated connections from one source to an authentication service within one window. "
    "Authentication outcomes are not visible in flow data, so no sub-technique is claimed.",
)
MITRE_SCAN = Mitre(
    "T1046",
    "Network Service Discovery",
    "One source contacted many distinct destination ports on one host within one window.",
)


@dataclass
class Finding:
    rule: str
    window_start: datetime
    window_end: datetime
    src_ip: str
    dst_ip: str
    summary: str
    flow_count: int
    mitre: Mitre | None
    src_asset_id: str | None
    dst_asset_id: str | None
    dst_ports: list[int] = field(default_factory=list)
    total_bytes: int = 0
    labels: Counter[str] = field(default_factory=Counter)

    @property
    def label_agreement(self) -> float | None:
        labelled = sum(self.labels.values())
        if not labelled:
            return None
        attacks = sum(n for label, n in self.labels.items() if label.upper() != BENIGN_LABEL)
        return attacks / labelled


@dataclass
class _Bucket:
    flows: int = 0
    ports: set[int] = field(default_factory=set)
    total_bytes: int = 0
    first: datetime | None = None
    last: datetime | None = None
    labels: Counter[str] = field(default_factory=Counter)
    src_asset: str | None = None
    dst_asset: str | None = None

    def add(self, row: Any) -> None:  # a SQLAlchemy Row of flow columns
        observed = row.observed_at
        self.flows += 1
        self.ports.add(row.dst_port)
        self.total_bytes += row.fwd_bytes + row.bwd_bytes
        self.first = observed if self.first is None else min(self.first, observed)
        self.last = observed if self.last is None else max(self.last, observed)
        if row.evaluation_label is not None:
            self.labels[row.evaluation_label] += 1
        self.src_asset = row.src_asset_id
        self.dst_asset = row.dst_asset_id


def _window(observed: datetime, minutes: int) -> datetime:
    floored = observed.replace(second=0, microsecond=0)
    return floored - timedelta(minutes=floored.minute % minutes)


def correlate(
    session: Session, source_id: str, thresholds: RuleThresholds | None = None
) -> list[Finding]:
    limits = thresholds or RuleThresholds()
    auth: dict[tuple[str, str, int, datetime], _Bucket] = defaultdict(_Bucket)
    scan: dict[tuple[str, str, datetime], _Bucket] = defaultdict(_Bucket)
    remote: dict[tuple[str, str, int, datetime], _Bucket] = defaultdict(_Bucket)
    findings: list[Finding] = []

    statement = (
        select(
            NetworkFlowRecord.observed_at,
            NetworkFlowRecord.src_ip,
            NetworkFlowRecord.dst_ip,
            NetworkFlowRecord.dst_port,
            NetworkFlowRecord.fwd_bytes,
            NetworkFlowRecord.bwd_bytes,
            NetworkFlowRecord.src_asset_id,
            NetworkFlowRecord.dst_asset_id,
            NetworkFlowRecord.dst_testbed_identity,
            NetworkFlowRecord.evaluation_label,
        )
        .where(NetworkFlowRecord.source_id == source_id)
        .execution_options(yield_per=20_000)
    )
    for row in session.execute(statement):
        window = _window(row.observed_at, limits.window_minutes)
        if row.dst_port in AUTH_PORTS:
            auth[(row.src_ip, row.dst_ip, row.dst_port, window)].add(row)
        scan[(row.src_ip, row.dst_ip, window)].add(row)
        outbound_external = row.dst_testbed_identity == EXTERNAL_INTERNET
        if outbound_external and row.dst_port not in COMMON_PORTS:
            remote[(row.src_ip, row.dst_ip, row.dst_port, window)].add(row)
        if outbound_external and row.fwd_bytes >= limits.volume_min_bytes:
            bucket = _Bucket()
            bucket.add(row)
            findings.append(
                _finding(
                    "volume",
                    bucket,
                    row.src_ip,
                    row.dst_ip,
                    f"Single outbound flow sent {row.fwd_bytes:,} bytes to an external host.",
                    None,
                    limits,
                )
            )

    for (src, dst, port, _), bucket in auth.items():
        if bucket.flows >= limits.brute_force_min_flows:
            findings.append(
                _finding(
                    "brute_force",
                    bucket,
                    src,
                    dst,
                    f"{bucket.flows} connections to {AUTH_PORTS[port]} (port {port}) "
                    f"within {limits.window_minutes} min.",
                    MITRE_BRUTE_FORCE,
                    limits,
                )
            )
    for (src, dst, _), bucket in scan.items():
        if len(bucket.ports) >= limits.port_scan_min_ports:
            findings.append(
                _finding(
                    "port_scan",
                    bucket,
                    src,
                    dst,
                    f"{len(bucket.ports)} distinct destination ports probed "
                    f"within {limits.window_minutes} min.",
                    MITRE_SCAN,
                    limits,
                )
            )
    for (src, dst, port, _), bucket in remote.items():
        if bucket.flows >= limits.remote_min_flows:
            findings.append(
                _finding(
                    "suspicious_remote",
                    bucket,
                    src,
                    dst,
                    f"{bucket.flows} flows to an external host on non-standard port {port}.",
                    None,
                    limits,
                )
            )
    findings.sort(key=lambda item: (item.window_start, item.rule, item.src_ip, item.dst_ip))
    return findings


def _finding(
    rule: str,
    bucket: _Bucket,
    src: str,
    dst: str,
    summary: str,
    mitre: Mitre | None,
    limits: RuleThresholds,
) -> Finding:
    assert bucket.first is not None and bucket.last is not None
    start = _window(bucket.first, limits.window_minutes)
    return Finding(
        rule=rule,
        window_start=start,
        window_end=start + timedelta(minutes=limits.window_minutes),
        src_ip=src,
        dst_ip=dst,
        summary=summary,
        flow_count=bucket.flows,
        mitre=mitre,
        src_asset_id=bucket.src_asset,
        dst_asset_id=bucket.dst_asset,
        dst_ports=sorted(bucket.ports)[:20],
        total_bytes=bucket.total_bytes,
        labels=bucket.labels,
    )
