# Recorded Real-World Data (CIC-IDS2017)

Status on 2026-10-18: **pipeline implemented and tested on fixtures; real-data
evaluation BLOCKED** until the dataset files are downloaded locally (the UNB
download page uses a request form and must be completed by a person). No real-data metric
is reported anywhere in this repository until that run happens.

## Source kinds

| Kind | Meaning | Status |
|---|---|---|
| `synthetic` | AegisArena's deterministic, seeded scenario engine | Active |
| `replay` | A recorded, labelled public capture imported from files. Shown as **Recorded replay**, never as live | Implemented |
| `live_readonly` | Live telemetry, read-only and recommendations-only | **Not implemented** (declared so the safety contract is explicit) |

`SIMULATION_ONLY=true` remains mandatory. Recorded data is analysed only: no
endpoint, CLI command or rule can turn a finding into a firewall, IAM,
Kubernetes or cloud change. The CLI refuses to run if `SIMULATION_ONLY` is off.

## Dataset and licence

CIC-IDS2017, Canadian Institute for Cybersecurity, University of New Brunswick.
The official UNB terms permit redistribution, republication and mirroring, but
require citation of the dataset and related paper. Cite:

> Iman Sharafaldin, Arash Habibi Lashkari, Ali A. Ghorbani. *Toward Generating a
> New Intrusion Detection Dataset and Intrusion Traffic Characterization.*
> ICISSP 2018.

AegisArena does not redistribute the data. `datasets/raw/` is git-ignored;
raw CSVs, the database and model artifacts (`*.joblib`) must never be committed.

## Getting the data (manual step)

1. Open the official UNB page at
   https://www.unb.ca/cic/datasets/ids-2017.html, use its **Download this
   dataset** form, and obtain `GeneratedLabelledFlows.zip`. Extract the
   **labelled-flow** CSVs (`TrafficLabelling`). The
   `MachineLearningCVE` CSVs drop IPs and timestamps and are rejected.
2. Place these two exact files required by AegisArena's acceptance test:

   ```
   datasets/raw/cicids2017/Monday-WorkingHours.pcap_ISCX.csv    (benign only)
   datasets/raw/cicids2017/Tuesday-WorkingHours.pcap_ISCX.csv   (FTP-/SSH-Patator)
   ```

3. From `backend/` (after `alembic upgrade head`):

   ```bash
   python -m app.ingestion import --adapter cicids2017 --file ../datasets/raw/cicids2017/Monday-WorkingHours.pcap_ISCX.csv
   python -m app.ingestion import --adapter cicids2017 --file ../datasets/raw/cicids2017/Tuesday-WorkingHours.pcap_ISCX.csv
   python -m app.ingestion list
   python -m app.ingestion evaluate --train <monday-source-id> --eval <tuesday-source-id>
   ```

4. Acceptance test (skipped as `BLOCKED` while the files are absent):

   ```bash
   pytest -q -s tests/test_cicids2017_acceptance.py
   ```

Results then appear on **Incidents → Data Sources** in the console.

## Pipeline

| Stage | Module | Notes |
|---|---|---|
| Canonical schema | `app/ingestion/canonical.py` | `CanonicalFlow`; `evaluation_label` is evaluation-only |
| CIC adapter | `app/ingestion/adapters/cicids2017.py` | Stripped/duplicate headers; layout check with a hint for ML-only CSVs |
| Canonical CSV/JSON | `app/ingestion/adapters/canonical_format.py` | ISO-8601 with offset required; `--dataset-name` and `--licence` required |
| Validation | `app/ingestion/validation.py` | Every rejection has a reason code |
| Import + dedup | `app/ingestion/importer.py` | Idempotent per file SHA-256; content fingerprint de-dup in-file and across sources |
| Asset mapping | `app/ingestion/asset_mapping.py` | Testbed identity and projected twin asset are separate fields |
| Persistence | migration `20261013_0019` | `data_sources`, `network_flows`, `network_flow_evaluations` |
| Features | `app/services/network_flow/features.py` | `network-flow-v1`; no labels, IPs, identities or timestamps |
| Detector + evaluation | `app/services/network_flow/evaluation_service.py` | IsolationForest, benign-only training |
| Correlation rules | `app/services/network_flow/correlation_service.py` | `network-flow-rules-v1` |
| API (read-only) | `app/api/routes/data_sources.py` | `GET /api/v1/data-sources[/{id}[/findings]]`, `/evaluations/latest` |
| UI | `frontend/src/pages/DataSourcesPage.tsx` | Source-kind badges, rejected/unmapped report, metrics |

Every row is accounted for: `rows_read = accepted + rejected + duplicate`.
Unmapped endpoints, afternoon-hour corrections and missing rates are counted
separately on accepted rows.

### Dataset quirks handled (never silently)

- **Timestamps** are day/month/year; afternoon hours appear on a 12-hour clock
  without AM/PM. Hours 1–7 are read as +12 h (capture ran during the working
  day) and counted as `rows_timestamp_adjusted`.
- **Timezone** is not in the file. It is assumed to be ADT (UTC−03:00), and
  that assumption is recorded on the source.
- **`Flow Bytes/s` / `Flow Packets/s`** are `Infinity`/`NaN` for zero-duration
  flows. They are stored as NULL and counted, never replaced. Features recompute
  rates from duration.
- **Negative durations** and malformed values are rejected with a reason code.
- **Repeated identical rows** are counted as duplicates.

### Twin mapping: identity vs projection

CIC testbed addresses map to a factual `testbed_identity` (from the dataset's
published testbed description). Some are additionally *projected* onto a twin
asset for display:

| Testbed host | Projected twin asset |
|---|---|
| Firewall NAT 172.16.0.1, firewall external, published attacker IPs | `external-user-01` |
| Web server 192.168.10.50 / 205.174.165.68 | `api-gateway-01` |
| Ubuntu server 192.168.10.51 / 205.174.165.66 | `application-pod-01` |
| DC/DNS 192.168.10.3 | `iam-service-01` |
| User workstations | none (identity only) |

A projection is a visual aid, not a claim that the CIC host *is* that cloud
asset. Attack traffic in the labelled flows mostly appears as 172.16.0.1
because external traffic is NATed by the testbed firewall.

## Evaluation protocol (`network-flow-isolation-forest-v1`)

Fixed before any real test data is seen and never tuned against test labels:

1. Training and evaluation must be different files.
2. If the training window is labelled, every label must be `BENIGN`.
3. Training flows are split by time: the first 80% fit the model and the last
   20% form a benign calibration window. Fit rows are thinned to at most
   200,000 by taking every k-th row, and k is recorded.
4. The threshold is the (1 − target FPR) quantile of calibration scores (default
   target 1%).
5. Evaluation labels are used only to compute metrics after scoring: ROC-AUC,
   average precision, precision, recall, F1, FPR, the confusion matrix and
   per-label detection rate.

Tests enforce the protocol. A threshold is unchanged when evaluation labels are
flipped; the evaluation refuses training data that contains attacks, or the
same file used twice; and features are unchanged when a label or IP changes.

## Correlation rules (`network-flow-rules-v1`)

Rules read flow fields only. Each finding shows `label_agreement`, the share of
its own flows labelled as attacks. That is an evaluation of the rule, never an
input to it.

| Rule | Evidence | MITRE |
|---|---|---|
| `brute_force` | ≥30 connections from one source to one auth service (FTP/SSH/Telnet/RDP/SMB/VNC) in 5 min | T1110 Brute Force (parent only; flows cannot show auth outcome) |
| `port_scan` | ≥50 distinct destination ports from one source to one host in 5 min | T1046 Network Service Discovery |
| `volume` | Single outbound flow ≥10 MB to an Internet host | Not mapped (too many benign explanations) |
| `suspicious_remote` | ≥20 flows to an Internet host on a non-standard port in 5 min | Not mapped |

The thresholds are engineering defaults chosen before any real data was seen.
They are not tuned.

## Known limitations

- The real-data run has not happened (BLOCKED on the manual download).
- Recorded flows are not yet fed into the synthetic replay engine, the twin
  playback or the Blue workflow. They have their own Data Sources view.
- No live collector exists. `live_readonly` is a declared, unimplemented kind.
- Only CIC-IDS2017 has a testbed identity map. Canonical-format imports get
  only an Internet/unknown classification.
- The recorded-data findings and optional twin projections are descriptive
  analysis only. They are not converted into synthetic scenario telemetry or
  accepted by the incident, prediction, Digital Twin state, response, or Blue
  Agent workflow services.
