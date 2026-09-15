# Authorization Matrix

This is the exhaustive, route-by-route inventory of every HTTP and
WebSocket endpoint in the AegisArena backend (`backend/app/api/routes/*.py`,
`backend/app/websocket/routes.py`, `backend/app/websocket/playback_routes.py`)
and the role required to call it, per `backend/app/core/auth.py`
(`Role.VIEWER < Role.ANALYST < Role.ADMIN`).

Enforcement mechanism: FastAPI `dependencies=[RequireViewer|RequireAnalyst|RequireAdmin]`
on the route decorator, except `PUT /api/v1/autonomy`, which uses
`RequireAnalyst` as its route dependency and then performs an additional
in-handler check requiring `Role.ADMIN` specifically when `mode=="autonomous"`
(see `backend/app/api/routes/autonomy.py`). Health endpoints have no auth
dependency at all, by design, so Azure Container Apps / Log Analytics can
probe them unauthenticated. See `docs/security/AUTHENTICATION.md` for the
Easy Auth trust-boundary assumption this all relies on.

Legend: **V** = VIEWER (anonymous allowed by default), **A** = ANALYST
(authenticated, non-anonymous), **AD** = ADMIN, **none** = no auth
dependency at all.

## health.py

| Method | Path | Role | Justification |
|---|---|---|---|
| GET | /health | none | Must remain unauthenticated for Azure Container Apps / Log Analytics liveness probing. |
| GET | /health/live | none | Same — liveness probe. |
| GET | /health/ready | none | Same — readiness probe. |

## system.py

| Method | Path | Role | Justification |
|---|---|---|---|
| GET | /api/system/status | V | Read-only system status; safe for anonymous demo access. |

## safety.py

| Method | Path | Role | Justification |
|---|---|---|---|
| GET | /api/safety | V | Read-only simulation-only/safety banner; non-sensitive. |

## simulation.py (`/api/v1/simulation`)

| Method | Path | Role | Justification |
|---|---|---|---|
| GET | /infrastructure | V | Read-only static asset inventory. |
| GET | /scenarios | V | Read-only scenario catalogue. |
| GET | /scenarios/{scenario_id} | V | Read-only scenario detail. |
| POST | /runs | A | Starts a simulation run (mutates state — generates and persists telemetry). |
| GET | /runs | V | Read-only list of runs. |
| GET | /runs/{run_id} | V | Read-only run detail. |
| GET | /runs/{run_id}/playback | V | Read-only playback metadata. |

## telemetry.py (`/api/v1/telemetry`)

| Method | Path | Role | Justification |
|---|---|---|---|
| GET | /events | V | Read-only telemetry query; no ingestion endpoint exists in this module. |
| GET | /events/{event_id} | V | Read-only telemetry detail. |

## detection.py (`/api/v1/detection`)

| Method | Path | Role | Justification |
|---|---|---|---|
| POST | /models/train | A | Trains and persists a new detection model (mutates state, consumes compute). |
| GET | /models | V | Read-only model list. |
| GET | /models/{model_id} | V | Read-only model detail. |
| POST | /runs/{run_id}/score | A | Triggers scoring of a run (mutates/persists assessments). |
| GET | /runs/{run_id}/assessments | V | Read-only assessment query. |
| POST | /models/{model_id}/evaluate | A | Triggers model evaluation (mutates/persists an evaluation record). |
| GET | /evaluations/{evaluation_id} | V | Read-only evaluation detail. |

## correlation.py (`/api/v1/correlation`)

| Method | Path | Role | Justification |
|---|---|---|---|
| POST | /runs/{run_id}/analyze | A | Triggers correlation analysis (mutates/persists incident candidates). |
| GET | /runs/{run_id}/incidents | V | Read-only incident list. |
| GET | /incidents/{candidate_id} | V | Read-only incident detail. |
| GET | /incidents/{candidate_id}/evidence | V | Read-only evidence list. |
| GET | /runs/{run_id}/techniques | V | Read-only MITRE technique-observation list. |

## prediction.py (`/api/v1/prediction`)

| Method | Path | Role | Justification |
|---|---|---|---|
| POST | /runs/{run_id}/analyze | A | Triggers prediction analysis (mutates/persists snapshots). |
| GET | /runs/{run_id}/snapshots | V | Read-only snapshot list. |
| GET | /runs/{run_id}/latest | V | Read-only latest snapshot. |
| GET | /snapshots/{snapshot_id} | V | Read-only snapshot detail. |
| GET | /snapshots/{snapshot_id}/hypotheses | V | Read-only hypothesis list. |
| POST | /runs/{run_id}/evaluate | A | Triggers prediction evaluation (mutates/persists an evaluation record). |
| GET | /evaluations/{evaluation_id} | V | Read-only evaluation detail. |

## mitre.py (`/api/v1/mitre`)

| Method | Path | Role | Justification |
|---|---|---|---|
| GET | /techniques | V | Static reference data (MITRE ATT&CK catalogue). |
| GET | /techniques/{technique_id} | V | Static reference data detail. |

## topology.py (`/api/v1/topology`)

| Method | Path | Role | Justification |
|---|---|---|---|
| GET | (root) | V | Read-only topology snapshot. |
| GET | /nodes | V | Read-only node list. |
| GET | /nodes/{asset_id} | V | Read-only node detail. |
| GET | /edges | V | Read-only edge list. |
| GET | /nodes/{asset_id}/neighbours | V | Read-only neighbourhood query. |
| GET | /paths | V | Read-only path query (expected/observed/correlated/predicted), no mutation. |
| GET | /runs/{run_id}/state | V | Read-only run-scoped topology state. |

## response.py (`/api/v1/response`)

| Method | Path | Role | Justification |
|---|---|---|---|
| GET | /playbooks | V | Static reference data (defensive playbooks). |
| GET | /playbooks/{playbook_id} | V | Static reference data detail. |
| POST | /runs/{run_id}/analyze | A | Triggers response analysis (mutates/persists recommendations). |
| GET | /runs/{run_id}/recommendations | V | Read-only recommendation list. |
| GET | /recommendations/{recommendation_id} | V | Read-only recommendation detail. |
| GET | /recommendations/{recommendation_id}/simulation | V | Read-only impact-simulation detail. |
| GET | /runs/{run_id}/summary | V | Read-only run summary. |

## orchestration.py (`/api/v1/orchestration`)

| Method | Path | Role | Justification |
|---|---|---|---|
| POST | /runs/{run_id}/create | A | Starts a response orchestration (mutates state). |
| GET | (root) | V | Read-only orchestration list. |
| GET | /{orchestration_id} | V | Read-only orchestration detail. |
| GET | /{orchestration_id}/plan | V | Read-only (alias of detail). |
| GET | /{orchestration_id}/decisions | V | Read-only (alias of detail). |
| POST | /{orchestration_id}/advance | A | Advances orchestration state machine (not an approval/rollback action). |
| POST | /{orchestration_id}/approvals/{approval_id}/decide | AD | Approves/rejects a high-impact response action — explicitly ADMIN-tier per spec. |
| POST | /{orchestration_id}/execute | A | Executes an already-approved plan step. |
| POST | /{orchestration_id}/verify | A | Runs post-execution verification (not an override). |
| POST | /{orchestration_id}/rollback | AD | Rollback of an executed response action — explicitly ADMIN-tier per spec. |
| GET | /{orchestration_id}/audit | V | Read-only audit trail. |
| GET | /{orchestration_id}/audit/verify | V | Read-only audit-chain integrity check (verifies, does not override). |

## attack_graph.py (`/api/v1/attack-graph`)

| Method | Path | Role | Justification |
|---|---|---|---|
| GET | /paths | V | Read-only attack-path analysis; no persisted mutation. |

## blast_radius.py (`/api/v1/blast-radius`)

| Method | Path | Role | Justification |
|---|---|---|---|
| POST | (root) | V | **Ambiguous method/role pairing, resolved to the more permissive-but-safe choice per rubric**: this is a POST only because the query payload doesn't fit query params — it is a pure read/what-if computation (`blast_radius_service.estimate`) with no persisted side effects, so it is classified VIEWER like the other read-only graph endpoints rather than ANALYST. |

## purple.py (`/api/v1/purple-team`)

| Method | Path | Role | Justification |
|---|---|---|---|
| GET | /scenarios | V | Read-only red-scenario summary list. |
| GET | /scenarios/{scenario_id}/definition | V | Read-only scenario definition. |
| POST | /experiments | A | Runs a purple-team experiment — explicitly ANALYST-tier per spec. |
| GET | /experiments | V | Read-only experiment list. |
| GET | /experiments/{experiment_id} | V | Read-only experiment detail. |

## agents.py (`/api/v1/agents`)

| Method | Path | Role | Justification |
|---|---|---|---|
| GET | (root) | V | Read-only agent registry list. |
| GET | /orchestrations/{orchestration_id}/trace | V | Read-only agent trace. |

## autonomy.py (`/api/v1/autonomy`)

| Method | Path | Role | Justification |
|---|---|---|---|
| GET | (root) | V | Read-only autonomy configuration. |
| PUT | (root), mode != autonomous | A | Non-AUTONOMOUS mode changes (observe/recommend/approval_required) are ordinary config changes. |
| PUT | (root), mode == autonomous | AD | Raising autonomy to AUTONOMOUS is the highest-impact configuration change in the system (agents may act without human approval) — explicitly ADMIN-tier per spec. Enforced via an in-handler check (see module docstring above) since both tiers share one endpoint. |

## blue_planning.py (`/api/v1/blue-planning`)

| Method | Path | Role | Justification |
|---|---|---|---|
| POST | /runs/{run_id}/compare | A | Blue-planning trigger — mutates/persists a plan-comparison assessment. |
| GET | /assessments/{assessment_id} | V | Read-only assessment detail. |

## policy.py (`/api/v1/policies`)

| Method | Path | Role | Justification |
|---|---|---|---|
| GET | (root) | V | Read-only static policy catalogue; no write/override endpoint exists in this module. |

## workflow.py (`/api/v1/workflow`)

| Method | Path | Role | Justification |
|---|---|---|---|
| POST | /runs/{run_id}/execute | A | Workflow trigger — mutates state (runs the full detect→respond coordinator). |

## evaluation.py (`/api/v1/evaluation`)

| Method | Path | Role | Justification |
|---|---|---|---|
| POST | /experiments | A | Creates and runs an experiment (mutates/persists state). |
| GET | /experiments | V | Read-only experiment list. |
| GET | /experiments/export.csv | V | Read-only export of existing experiment data. |
| GET | /experiments/export.json | V | Read-only export of existing experiment data. |
| GET | /experiments/{experiment_id} | V | Read-only experiment detail. |
| POST | /experiments/{experiment_id}/rerun | A | Creates and runs a new experiment (mutates/persists state). |
| GET | /experiments/{experiment_id}/metrics | V | Read-only metrics. |
| GET | /experiments/{experiment_id}/timeline | V | Read-only timeline. |
| GET | /experiments/{experiment_id}/report | V | Read-only faculty report. |
| POST | /batches | A | Runs a full scenario x seed x defence_mode matrix synchronously (mutates/persists state). |
| GET | /batches | V | Read-only batch list. |
| GET | /batches/{batch_id} | V | Read-only batch detail. |
| POST | /robustness | A | Runs a baseline/perturbed experiment pair (mutates/persists state). |
| GET | /compare | V | Read-only mode comparison. |
| GET | /aggregate | V | Read-only aggregation across experiments. |

## WebSocket routes

| Path | Role | Justification |
|---|---|---|
| WS /ws/events | Public, read-only (V) | Intentionally public event stream; no state-changing actions exposed over it. Browsers cannot reliably attach custom auth headers to WebSocket handshakes, so the connection is left ungated at the FastAPI layer — see the inline comment in `backend/app/websocket/routes.py` and `docs/security/AUTHENTICATION.md`. |
| WS /api/v1/ws/simulation/runs/{run_id} | Public, read-only (V) | Intentionally public playback stream of already-recorded run telemetry/detection/correlation/prediction data; only accepts playback control messages (pause/resume/seek), no state-changing actions. Same rationale as `/ws/events` — see the inline comment in `backend/app/websocket/playback_routes.py`. |

## Summary of ambiguous calls made (most-secure-reasonable default)

- `POST /api/v1/blast-radius` — POST method suggested a mutation, but the
  handler is a pure read/what-if computation with no persistence.
  Classified VIEWER, consistent with the rubric's explicit "blast radius"
  read-only guidance, not with the HTTP method.
- `PUT /api/v1/autonomy` — a single endpoint serves both an ordinary
  ANALYST-tier config change and the ADMIN-tier "raise to AUTONOMOUS"
  action. Rather than gate the whole endpoint at ADMIN (which would be
  more restrictive than the spec's intent for non-AUTONOMOUS changes) or
  at ANALYST (which would under-protect the AUTONOMOUS transition), the
  route requires ANALYST at minimum and performs an explicit in-handler
  ADMIN check specifically for `mode == "autonomous"`.
- `POST /api/v1/orchestration/{id}/execute` and `.../verify` — classified
  ANALYST rather than ADMIN. They are ordinary state-machine steps ("run
  the already-approved action", "check the result"), not the approval
  decision itself (`.../approvals/{id}/decide`, ADMIN) or a rollback
  override (`.../rollback`, ADMIN).
