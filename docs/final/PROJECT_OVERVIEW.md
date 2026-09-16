# AegisArena — Project Overview

## Problem

Cloud security teams struggle to answer, with evidence rather than intuition:
*if this attack happened, what would actually break, would our automated
response help or hurt, and can we prove recovery worked?* Most tooling
either stops at detection, or asks a human to reason about blast radius and
response tradeoffs by hand. AegisArena is a research testbed that models the
whole loop — attack, detection, exposure reasoning, defensive
decision-making, safe execution, and independent verification — entirely in
simulation, so the loop can be run repeatedly, measured, and compared across
strategies without touching a real cloud.

## Simulation-only boundary

AegisArena never performs a real attack, a real IAM mutation, a real
firewall change, or a real credential revocation. Every Red Agent action,
every Blue Agent response, and every "execution" is a synthetic mutation
against an in-memory digital twin of a cloud environment — never a live
resource. This boundary is enforced in code (`SIMULATION_ONLY` must be
`true` or the backend refuses to start) and repeated throughout the UI. Azure
is used only to *host* this simulation as a web application; Azure is never
the target of anything the system does.

## Architecture at a glance

```
Red Agent (synthetic adversary)
   → Telemetry
   → Detection (Isolation Forest)
   → Incident Correlation
   → MITRE ATT&CK Mapping
   → Attack Graph / Blast Radius
   → Blue Agent response planning
   → Digital Twin what-if simulation
   → Policy / Safety Governor
   → Approval routing (or autonomous execution)
   → Synthetic Execution
   → Independent Verification (rollback if it fails)
   → Resilience measurement (Evaluation: ARS, MCI)
```

- **Digital Twin**: an in-memory graph of synthetic cloud assets and their
  relationships. Attacks and responses mutate a twin-local copy of state,
  never the immutable base topology, so "what happened" and "what the twin
  predicts" are always distinguishable.
- **Red side**: one agent — the Synthetic Red Agent / Scenario Engine — plays
  deterministic, seeded attack scenarios.
- **Analytical subsystems** (not agents): Telemetry, Detection, Incident
  Correlation, MITRE ATT&CK Mapping, Attack Graph, and Blast Radius. These
  feed evidence to the agents; they do not make decisions themselves.
- **Blue side**: six deterministic software agents — Response Planner,
  Impact Simulation, Safety Governor, Approval Router, Synthetic Execution,
  and Verification — that plan, gate, execute, and check a response in that
  order. None of them are LLM chatbots; every decision is a deterministic
  function of persisted state, recorded as an auditable `AgentDecision`.
- **Evaluation**: a reproducible experiment framework that runs the same
  scenario/seed against four isolated defence baselines and scores each with
  the Aegis Resilience Score (ARS) and Mission Continuity Index (MCI).

## Technology stack

- **Backend**: FastAPI, SQLAlchemy, Alembic, WebSockets, scikit-learn
  (Isolation Forest). SQLite for local development/tests, PostgreSQL for
  production (Azure Database for PostgreSQL Flexible Server).
- **Frontend**: React 19, Vite 7, TypeScript.
- **Auth/RBAC**: VIEWER/ANALYST/ADMIN roles, backend-enforced, designed to
  sit behind Azure Container Apps Easy Auth (not yet enabled — see
  `docs/security/AUTHENTICATION.md`).
- **Hosting target**: Azure Container Apps (Consumption), Azure Container
  Registry, Azure Database for PostgreSQL Flexible Server, Key Vault, Log
  Analytics — see `docs/deployment/AZURE_ARCHITECTURE.md`. Not yet deployed;
  hosting is a deliberate final step after this review.

## Where to look next

- `docs/final/RESEARCH_CONTRIBUTIONS.md` — what is actually novel here.
- `docs/final/FACULTY_DEMO.md` — the exact screen-by-screen walkthrough.
- `docs/final/FEATURE_MAP.md` — capability → UI page → backend subsystem.
- `docs/final/LIMITATIONS_AND_FUTURE_WORK.md` — honest constraints.
