"""Builders for small *fixture* files in the CIC-IDS2017 labelled-flow layout.

The header reproduces the real TrafficLabelling CSV column order, including
the leading spaces and the duplicated "Fwd Header Length". Row values are
hand-made test fixtures - never presented as dataset results.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path

CIC_HEADER = [
    "Flow ID", " Source IP", " Source Port", " Destination IP", " Destination Port",
    " Protocol", " Timestamp", " Flow Duration", " Total Fwd Packets",
    " Total Backward Packets", "Total Length of Fwd Packets", " Total Length of Bwd Packets",
    " Fwd Packet Length Max", " Fwd Packet Length Min", " Fwd Packet Length Mean",
    " Fwd Packet Length Std", "Bwd Packet Length Max", " Bwd Packet Length Min",
    " Bwd Packet Length Mean", " Bwd Packet Length Std", "Flow Bytes/s", " Flow Packets/s",
    " Flow IAT Mean", " Flow IAT Std", " Flow IAT Max", " Flow IAT Min", "Fwd IAT Total",
    " Fwd IAT Mean", " Fwd IAT Std", " Fwd IAT Max", " Fwd IAT Min", "Bwd IAT Total",
    " Bwd IAT Mean", " Bwd IAT Std", " Bwd IAT Max", " Bwd IAT Min", "Fwd PSH Flags",
    " Bwd PSH Flags", " Fwd URG Flags", " Bwd URG Flags", " Fwd Header Length",
    " Bwd Header Length", "Fwd Packets/s", " Bwd Packets/s", " Min Packet Length",
    " Max Packet Length", " Packet Length Mean", " Packet Length Std",
    " Packet Length Variance", "FIN Flag Count", " SYN Flag Count", " RST Flag Count",
    " PSH Flag Count", " ACK Flag Count", " URG Flag Count", " CWE Flag Count",
    " ECE Flag Count", " Down/Up Ratio", " Average Packet Size", " Avg Fwd Segment Size",
    " Avg Bwd Segment Size", " Fwd Header Length", "Fwd Avg Bytes/Bulk",
    " Fwd Avg Packets/Bulk", " Fwd Avg Bulk Rate", " Bwd Avg Bytes/Bulk",
    " Bwd Avg Packets/Bulk", "Bwd Avg Bulk Rate", "Subflow Fwd Packets",
    " Subflow Fwd Bytes", " Subflow Bwd Packets", " Subflow Bwd Bytes",
    "Init_Win_bytes_forward", " Init_Win_bytes_backward", " act_data_pkt_fwd",
    " min_seg_size_forward", "Active Mean", " Active Std", " Active Max", " Active Min",
    "Idle Mean", " Idle Std", " Idle Max", " Idle Min", " Label",
]  # fmt: skip


@dataclass
class FixtureFlow:
    src: str
    sport: int
    dst: str
    dport: int
    timestamp: str
    duration_us: str = "1000"
    fwd_packets: str = "2"
    bwd_packets: str = "1"
    fwd_bytes: str = "120"
    bwd_bytes: str = "60"
    bytes_rate: str = "180000"
    packets_rate: str = "3000"
    syn: str = "1"
    fin: str = "0"
    rst: str = "0"
    psh: str = "0"
    ack: str = "1"
    label: str = "BENIGN"
    protocol: str = "6"


def row(flow: FixtureFlow) -> list[str]:
    values = {name.strip(): "0" for name in CIC_HEADER}
    values.update(
        {
            "Flow ID": f"{flow.src}-{flow.dst}-{flow.sport}-{flow.dport}-{flow.protocol}",
            "Source IP": flow.src,
            "Source Port": str(flow.sport),
            "Destination IP": flow.dst,
            "Destination Port": str(flow.dport),
            "Protocol": flow.protocol,
            "Timestamp": flow.timestamp,
            "Flow Duration": flow.duration_us,
            "Total Fwd Packets": flow.fwd_packets,
            "Total Backward Packets": flow.bwd_packets,
            "Total Length of Fwd Packets": flow.fwd_bytes,
            "Total Length of Bwd Packets": flow.bwd_bytes,
            "Flow Bytes/s": flow.bytes_rate,
            "Flow Packets/s": flow.packets_rate,
            "FIN Flag Count": flow.fin,
            "SYN Flag Count": flow.syn,
            "RST Flag Count": flow.rst,
            "PSH Flag Count": flow.psh,
            "ACK Flag Count": flow.ack,
            "Label": flow.label,
        }
    )
    return [values[name.strip()] for name in CIC_HEADER]


def write_cic(
    path: Path, flows: list[FixtureFlow], extra_rows: list[list[str]] | None = None
) -> Path:
    with path.open("w", newline="", encoding="latin-1") as handle:
        writer = csv.writer(handle)
        writer.writerow(CIC_HEADER)
        for flow in flows:
            writer.writerow(row(flow))
        for extra in extra_rows or []:
            writer.writerow(extra)
    return path


def benign_day(seed: int, count: int, day: str) -> list[FixtureFlow]:
    """Varied web/DNS-like fixture flows between workstations, servers and the Internet."""

    rng = random.Random(seed)
    hosts = ["192.168.10.5", "192.168.10.9", "192.168.10.14", "192.168.10.25"]
    flows = []
    for index in range(count):
        port = rng.choice([80, 443, 443, 53])
        minute = 9 * 60 + index * 300 // count
        fwd_packets = rng.randint(3, 40)
        bwd_packets = rng.randint(2, 60)
        flows.append(
            FixtureFlow(
                src=rng.choice(hosts),
                sport=rng.randint(49152, 65000),
                dst=rng.choice(["192.168.10.3", "192.168.10.50", "23.1.2.3", "8.8.8.8"]),
                dport=port,
                timestamp=f"{day} {minute // 60}:{minute % 60:02d}",
                duration_us=str(rng.randint(20_000, 5_000_000)),
                fwd_packets=str(fwd_packets),
                bwd_packets=str(bwd_packets),
                fwd_bytes=str(fwd_packets * rng.randint(40, 600)),
                bwd_bytes=str(bwd_packets * rng.randint(60, 1400)),
                syn=str(1),
                fin=str(1),
                psh=str(rng.randint(0, 3)),
                ack=str(rng.randint(1, 30)),
                protocol="17" if port == 53 else "6",
            )
        )
    return flows


def ssh_patator(count: int, day: str, start_minute: int = 10 * 60) -> list[FixtureFlow]:
    """Short, repetitive fixture flows to SSH through the firewall NAT."""

    return [
        FixtureFlow(
            src="172.16.0.1",
            sport=40000 + index,
            dst="192.168.10.50",
            dport=22,
            timestamp=f"{day} {(start_minute + index // 20) // 60}:"
            f"{(start_minute + index // 20) % 60:02d}",
            duration_us=str(3_000_000 + index),
            fwd_packets="11",
            bwd_packets="16",
            fwd_bytes="1200",
            bwd_bytes="2400",
            syn="0",
            fin="1",
            psh="8",
            ack="26",
            label="SSH-Patator",
        )
        for index in range(count)
    ]
