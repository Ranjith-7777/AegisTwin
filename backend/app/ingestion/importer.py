"""Import one recorded telemetry file into `data_sources` + `network_flows`.

Streaming and chunked, so a 500k-row CIC-IDS2017 day never sits in memory
as ORM objects. Idempotent per file: the source id is derived from the file's
SHA-256, and re-importing the same bytes returns the existing source without
writing anything.

Every row ends up in exactly one bucket - accepted, rejected (with a reason
code), or duplicate - so `rows_read == accepted + rejected + duplicate`.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid5

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.database.models import DataSourceRecord, NetworkFlowRecord
from app.ingestion.adapters import canonical_format, cicids2017
from app.ingestion.asset_mapping import CICIDS2017_TESTBED, KnownHost, map_endpoint
from app.ingestion.canonical import CanonicalFlow, SourceKind
from app.ingestion.validation import RowRejected

SOURCE_NAMESPACE = UUID("0b6f2f0e-6a43-4c71-9a55-6e9f4f1b2c19")
CHUNK_SIZE = 2000
TOP_UNMAPPED = 25


class ImportRefused(ValueError):
    """The import request itself is invalid (not a row-level problem)."""


@dataclass(frozen=True)
class ImportResult:
    source: DataSourceRecord
    created: bool


@dataclass(frozen=True)
class _AdapterSpec:
    name: str
    dataset_name: str
    licence: str
    citation: str | None
    notes: tuple[str, ...]
    testbed: dict[str, KnownHost]


def _adapter(adapter: str, dataset_name: str | None, licence: str | None) -> _AdapterSpec:
    if adapter == cicids2017.ADAPTER_NAME:
        return _AdapterSpec(
            name=adapter,
            dataset_name=cicids2017.DATASET_NAME,
            licence=cicids2017.LICENCE,
            citation=cicids2017.CITATION,
            notes=(
                cicids2017.TIMEZONE_NOTE,
                "Afternoon hours written without AM/PM are read as +12h (rows_timestamp_adjusted).",
                "Endpoint projection onto twin assets is a visual mapping, not an identity.",
            ),
            testbed=CICIDS2017_TESTBED,
        )
    if adapter == canonical_format.ADAPTER_NAME:
        if not dataset_name or not licence:
            raise ImportRefused(
                "The canonical adapter needs --dataset-name and --licence so provenance "
                "is never blank."
            )
        return _AdapterSpec(
            name=adapter,
            dataset_name=dataset_name,
            licence=licence,
            citation=None,
            notes=("Canonical-format import; no testbed identity map applied.",),
            testbed={},
        )
    raise ImportRefused(f"Unknown adapter '{adapter}'.")


def _rows(adapter: str, path: Path) -> Iterator[CanonicalFlow | RowRejected]:
    if adapter == cicids2017.ADAPTER_NAME:
        return cicids2017.read_rows(path)
    return canonical_format.read_rows(path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def import_file(
    session: Session,
    path: Path,
    adapter: str,
    imported_by: str,
    source_kind: SourceKind = SourceKind.REPLAY,
    dataset_name: str | None = None,
    licence: str | None = None,
) -> ImportResult:
    if source_kind is not SourceKind.REPLAY:
        # Recorded files are replays by definition; synthetic data comes from
        # the scenario engine and live telemetry has no collector (read-only
        # design documented, not implemented).
        raise ImportRefused("Only recorded datasets (source_kind=replay) can be imported.")
    if not path.is_file():
        raise ImportRefused(f"File not found: {path}")
    spec = _adapter(adapter, dataset_name, licence)

    sha = file_sha256(path)
    existing = session.scalar(select(DataSourceRecord).where(DataSourceRecord.file_sha256 == sha))
    if existing is not None:
        return ImportResult(existing, created=False)

    source = DataSourceRecord(
        source_id=str(uuid5(SOURCE_NAMESPACE, sha)),
        source_kind=source_kind.value,
        adapter=spec.name,
        dataset_name=spec.dataset_name,
        file_name=path.name,
        file_sha256=sha,
        file_bytes=path.stat().st_size,
        licence=spec.licence,
        citation=spec.citation,
        provenance_notes_json=list(spec.notes),
        rows_read=0,
        rows_accepted=0,
        rows_rejected=0,
        rows_duplicate=0,
        rows_unmapped=0,
        rows_timestamp_adjusted=0,
        rows_rate_missing=0,
        rejection_reasons_json={},
        unmapped_endpoints_json={},
        label_counts_json={},
        imported_by=imported_by,
    )
    session.add(source)
    session.flush()

    try:
        _ingest(session, source, path, spec)
    except Exception:
        session.rollback()
        raise
    session.commit()
    return ImportResult(source, created=True)


def _ingest(session: Session, source: DataSourceRecord, path: Path, spec: _AdapterSpec) -> None:
    rejections: Counter[str] = Counter()
    unmapped: Counter[str] = Counter()
    labels: Counter[str] = Counter()
    seen: set[str] = set()
    pending: dict[str, dict[str, object]] = {}
    counts = Counter[str]()
    window_start: datetime | None = None
    window_end: datetime | None = None

    def flush() -> None:
        if not pending:
            return
        already = set(
            session.scalars(
                select(NetworkFlowRecord.flow_id).where(NetworkFlowRecord.flow_id.in_(pending))
            )
        )
        rows = [row for flow_id, row in pending.items() if flow_id not in already]
        counts["duplicate"] += len(already)
        counts["accepted"] -= len(already)
        for flow_id in already:
            label = pending[flow_id]["evaluation_label"]
            if isinstance(label, str):
                labels[label] -= 1
        if rows:
            session.execute(insert(NetworkFlowRecord), rows)
        pending.clear()

    for item in _rows(spec.name, path):
        counts["read"] += 1
        if isinstance(item, RowRejected):
            rejections[item.reason] += 1
            continue
        fingerprint = item.fingerprint()
        if fingerprint in seen:
            counts["duplicate"] += 1
            continue
        seen.add(fingerprint)

        src = map_endpoint(item.src_ip, spec.testbed)
        dst = map_endpoint(item.dst_ip, spec.testbed)
        if src.testbed_identity is None or dst.testbed_identity is None:
            counts["unmapped"] += 1
            for ip, mapping in ((item.src_ip, src), (item.dst_ip, dst)):
                if mapping.testbed_identity is None:
                    unmapped[ip] += 1
        if item.timestamp_adjusted:
            counts["adjusted"] += 1
        if item.flow_bytes_per_s is None or item.flow_packets_per_s is None:
            counts["rate_missing"] += 1
        if item.evaluation_label is not None:
            labels[item.evaluation_label] += 1
        window_start = (
            item.observed_at if window_start is None else min(window_start, item.observed_at)
        )
        window_end = item.observed_at if window_end is None else max(window_end, item.observed_at)

        counts["accepted"] += 1
        pending[fingerprint] = {
            "flow_id": fingerprint,
            "source_id": source.source_id,
            "row_number": item.row_number,
            "observed_at": item.observed_at,
            "src_ip": item.src_ip,
            "src_port": item.src_port,
            "dst_ip": item.dst_ip,
            "dst_port": item.dst_port,
            "protocol": item.protocol,
            "duration_s": item.duration_s,
            "fwd_packets": item.fwd_packets,
            "bwd_packets": item.bwd_packets,
            "fwd_bytes": item.fwd_bytes,
            "bwd_bytes": item.bwd_bytes,
            "syn_count": item.syn_count,
            "fin_count": item.fin_count,
            "rst_count": item.rst_count,
            "psh_count": item.psh_count,
            "ack_count": item.ack_count,
            "flow_bytes_per_s": item.flow_bytes_per_s,
            "flow_packets_per_s": item.flow_packets_per_s,
            "src_testbed_identity": src.testbed_identity,
            "dst_testbed_identity": dst.testbed_identity,
            "src_asset_id": src.projected_asset_id,
            "dst_asset_id": dst.projected_asset_id,
            "evaluation_label": item.evaluation_label,
        }
        if len(pending) >= CHUNK_SIZE:
            flush()
    flush()

    source.rows_read = counts["read"]
    source.rows_accepted = counts["accepted"]
    source.rows_rejected = sum(rejections.values())
    source.rows_duplicate = counts["duplicate"]
    source.rows_unmapped = counts["unmapped"]
    source.rows_timestamp_adjusted = counts["adjusted"]
    source.rows_rate_missing = counts["rate_missing"]
    source.rejection_reasons_json = dict(sorted(rejections.items()))
    source.unmapped_endpoints_json = dict(unmapped.most_common(TOP_UNMAPPED))
    source.label_counts_json = {label: n for label, n in sorted(labels.items()) if n > 0}
    source.window_start = window_start
    source.window_end = window_end
