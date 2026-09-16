# Feature Map

Major capabilities mapped to where they live in the UI, which backend
subsystem implements them, and why they exist from a research standpoint.

| Capability | UI page(s) | Backend subsystem | Research purpose |
|---|---|---|---|
| System posture summary | Command Centre (`/`) | `system`, `safety` routes; derived client-side in `lib/commandCentre.ts` | Single-glance mission/cloud state — the "10-second understanding" entry point |
| Synthetic scenario engine | Command Centre (Red Agent rail), `/telemetry` | `simulation`, `telemetry` routes; Synthetic Red Agent / Scenario Engine | Deterministic, seeded threat-informed adversary emulation |
| Anomaly detection | `/model-analytics` | `detection` routes; scikit-learn Isolation Forest | ML-based telemetry scoring feeding correlation |
| Incident correlation | `/incidents` | `correlation` routes | Groups scored telemetry into incident candidates with evidence |
| MITRE ATT&CK mapping | `/mitre` | `mitre` routes | Maps observed techniques to the ATT&CK framework for analyst context |
| Next-stage attack prediction | `/predictive-analytics` | `prediction` routes | Forward-looking hypothesis generation from correlated evidence |
| Digital Twin topology | `/digital-twin` (Topology tab) | `topology` routes; in-memory twin graph | Graph-based reasoning substrate for exposure/blast-radius |
| Attack path analysis | `/digital-twin` (Attack Paths tab) | `attack_graph` routes | Graph-based exposure reasoning — what a technique can actually reach |
| Blast radius | `/digital-twin` (Blast Radius tab) | `blast_radius` routes | Quantifies affected assets, not a generic severity label |
| Purple team experiments | `/digital-twin` (Purple Team tab) | `purple` routes | Combined red/blue scripted experiments for controlled evidence |
| Response planning & ranking | Command Centre (Blue Agent card), `/blue-agent/response-plans` | `response`, `blue_planning` routes; Response Planner Agent | Candidate defensive actions ranked by Response Utility Score |
| Digital Twin what-if simulation | `/digital-twin` ("Show simulated response impact"), `/blue-agent/response-plans` | `response` routes (impact simulation); Impact Simulation Agent | Counterfactual defensive simulation before any real execution |
| Policy / safety evaluation | `/blue-agent/policies` | `policy` routes; Safety Governor Agent | Policy-as-code gate independent of the raw response score |
| Approval routing / autonomy mode | `/blue-agent/overview`, `/blue-agent/verification` | `autonomy`, `orchestration` routes; Approval Router Agent | Human-in-the-loop vs. autonomous execution, explicitly configurable |
| Synthetic execution | `/digital-twin` ("Show applied synthetic execution"), `/blue-agent/agent-workflow` | `orchestration` routes; Synthetic Execution Agent | Applies the authorized plan's mutation to the twin only |
| Independent verification & rollback | `/blue-agent/verification` | `orchestration`, `workflow` routes; Verification Agent | Confirms (or fails and reverts) the response, never assumed |
| Full agent decision trace | `/blue-agent/agent-workflow` | `agents` routes; all seven agents | Auditable "why did the system decide this" evidence |
| Multi-baseline resilience evaluation | `/evaluation`, `/evaluation/experiments`, `/evaluation/compare`, `/evaluation/aggregate`, `/evaluation/batches` | `evaluation` routes; `services/evaluation/` | Reproducible ARS/MCI comparison across the four defence baselines |
| Audit trail | `/audit-trail` | `orchestration` routes (audit events) | Tamper-evident, hash-chained record of every agent/human action |
| Authentication & authorization | All pages (backend-enforced) | `app.core.auth`; every route's `dependencies=[...]` | VIEWER/ANALYST/ADMIN least-privilege enforcement (Phase 6) |

For the full per-route VIEWER/ANALYST/ADMIN breakdown, see
`docs/security/AUTHORIZATION_MATRIX.md`. For the exact seven-agent registry
(names, roles, versions), see `/blue-agent/agent-workflow` live or
`backend/app/services/agent_registry_service.py`.
