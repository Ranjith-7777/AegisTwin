"""Network-flow feature profile `network-flow-v1`.

Built only from per-flow behaviour (sizes, counts, rates, flags, protocol
and a coarse destination-port class). Deliberately excluded:

* `evaluation_label` - ground truth, evaluation only (guarded by a test).
* IP addresses and testbed identities - would let a model memorise which
  host is the attacker in one capture instead of learning behaviour.
* timestamps - capture-day artefacts, not behaviour.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

FEATURE_SCHEMA_VERSION = "network-flow-v1"

FEATURE_NAMES: tuple[str, ...] = (
    "log_duration_s",
    "log_fwd_packets",
    "log_bwd_packets",
    "log_fwd_bytes",
    "log_bwd_bytes",
    "log_bytes_per_s",
    "log_packets_per_s",
    "bwd_fwd_byte_ratio",
    "log_mean_fwd_packet_bytes",
    "log_mean_bwd_packet_bytes",
    "log_syn_count",
    "log_fin_count",
    "log_rst_count",
    "log_psh_count",
    "log_ack_count",
    "proto_tcp",
    "proto_udp",
    "port_well_known",
    "port_registered",
    "port_dynamic",
)

# Columns that must never become features (checked by tests).
FORBIDDEN_FEATURE_SOURCES = frozenset(
    {
        "evaluation_label",
        "src_ip",
        "dst_ip",
        "src_testbed_identity",
        "dst_testbed_identity",
        "src_asset_id",
        "dst_asset_id",
        "observed_at",
    }
)


class FlowLike(Protocol):
    duration_s: float
    fwd_packets: int
    bwd_packets: int
    fwd_bytes: int
    bwd_bytes: int
    syn_count: int
    fin_count: int
    rst_count: int
    psh_count: int
    ack_count: int
    protocol: int
    dst_port: int


def _log(value: float) -> float:
    return math.log1p(max(value, 0.0))


def flow_features(flow: FlowLike) -> list[float]:
    packets = flow.fwd_packets + flow.bwd_packets
    total_bytes = flow.fwd_bytes + flow.bwd_bytes
    # Rates are recomputed from duration rather than read from the source,
    # so zero-duration flows get a defined value instead of Infinity.
    duration = max(flow.duration_s, 1e-6)
    port = flow.dst_port
    return [
        _log(flow.duration_s),
        _log(flow.fwd_packets),
        _log(flow.bwd_packets),
        _log(flow.fwd_bytes),
        _log(flow.bwd_bytes),
        _log(total_bytes / duration),
        _log(packets / duration),
        flow.bwd_bytes / (flow.fwd_bytes + flow.bwd_bytes + 1),
        _log(flow.fwd_bytes / flow.fwd_packets) if flow.fwd_packets else 0.0,
        _log(flow.bwd_bytes / flow.bwd_packets) if flow.bwd_packets else 0.0,
        _log(flow.syn_count),
        _log(flow.fin_count),
        _log(flow.rst_count),
        _log(flow.psh_count),
        _log(flow.ack_count),
        1.0 if flow.protocol == 6 else 0.0,
        1.0 if flow.protocol == 17 else 0.0,
        1.0 if port < 1024 else 0.0,
        1.0 if 1024 <= port < 49152 else 0.0,
        1.0 if port >= 49152 else 0.0,
    ]


def feature_matrix(flows: Sequence[FlowLike]) -> NDArray[np.float64]:
    if not flows:
        return np.zeros((0, len(FEATURE_NAMES)), dtype=np.float64)
    return np.asarray([flow_features(flow) for flow in flows], dtype=np.float64)
