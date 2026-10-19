# Faculty Demo Guide

A deterministic, presentation-friendly walkthrough of AegisArena, runnable
entirely locally — no Azure required.

## Prerequisites

- Docker (recommended, matches production-parity setup), **or** Python 3.11+
  and Node 24+ installed locally.
- No Azure account, credentials, or network access needed.

## Starting the system

**Option A — Docker Compose (simplest):**

```bash
docker compose up
```

Backend: `http://localhost:8000`. Frontend: `http://localhost:5173`. Wait
for the backend healthcheck to pass (compose waits for you automatically)
before opening the frontend.

**Option B — run directly:**

```bash
# Backend
cd backend
python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt -r requirements-dev.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`.

## Demo scenario

Use the built-in **`staged-compromise-demo`** scenario — a deterministic,
seeded attack scenario chosen specifically for this kind of walkthrough
(it is the default preselected scenario/seed when `DEMO_MODE` is enabled;
see `frontend/src/pages/RedAgentOverviewPage.tsx`). Recommended
seed: `84`. Recommended playback speed: `50×` so the run completes in well
under a minute of real time instead of requiring the presenter to wait.

## Exact screen flow

1. **Command Centre (`/app`)** — Start here. Point out the persisted cloud
   topology and the honest empty-state values before a run exists.
2. Open **Workflow & Agents (`/workflow`)**, select **Autonomous**, and confirm
   the simulation-only autonomy change.
3. Open **Red Agent (`/red-agent`)**, select `staged-compromise-demo`, seed
   `84`, speed `50×`, leave detection/correlation/prediction enabled, and click
   **Launch scenario**.
4. Return to **Command Centre**. Watch the posture and activity move from
   replay through anomaly, incident, response, and verified containment.
5. Open **Digital Twin (`/digital-twin`)**. Show
   the topology view, then the **Attack Paths** and **Blast Radius** tabs —
   this is where to say "the system is reasoning about the graph, not
   guessing from a severity table."
6. Open **Incidents** and **MITRE ATT&CK** to show the
   correlated incident, its priority/evidence, and the mapped ATT&CK
   techniques.
7. Open **Agent Workflow (`/blue-agent/agent-workflow`)** and
   select the current orchestration from the "Live agent trace" dropdown.
   This is the strongest research-facing screen: it shows every one of the
   six Blue agents' decisions in order — Response Planner, Impact
   Simulation, Safety Governor, Approval Router, Synthetic Execution,
   Verification — each with its rationale and any warnings. Say: *"this is
   not a black box; every decision here is deterministic and auditable."*
8. Return to **Workflow & Agents** and click **Evaluate completed run**. The
   resulting faculty report is computed from the original persisted run,
   incident, orchestration, execution and verification evidence; it does not
   replay the attack. Show MCI, ARS decomposition and reproduction metadata.
9. Open **Response Plans**, **Verification**, and **Audit Trail** to show the
   selected action, expected-versus-observed result and valid hash chain.
10. Optionally open **Evaluation** to show independent four-strategy benchmark
    experiments. Do not run the full 80-experiment canonical matrix during a
    live demo; one ad-hoc experiment is enough if no benchmark data exists.

## What to say on each page

- **Command Centre**: "This is the single pane of glass — cloud state,
  active threat, digital twin, blue response, and resilience score, all in
  one place."
- **Digital Twin**: "Everything here is a synthetic graph the system
  actually reasons over — attack paths and blast radius are computed, not
  asserted."
- **Agent Workflow**: "Six deterministic agents, not one black-box model —
  every decision is logged and auditable."
- **Evaluation**: "The same scenario is scored under four different defence
  strategies so the value of the agentic approach is measured, not
  assumed."

## Expected observable evidence

- A non-zero Risk Score and at least one entry in Recent Activity within
  seconds of starting the scenario.
- A correlated incident with MITRE technique mappings.
- A ranked Blue Agent recommendation with a numeric Defense Score.
- A full six-agent decision trace on the Agent Workflow page.
- A completed-workflow report with a numeric ARS (0–100), MCI, versioned
  formulas and source-evidence identifiers.

## Recovery if a step fails

- **Scenario won't start**: check a detection model exists (Model Analytics
  page → "Create one in Detection Models" link on the Red Agent panel if
  none exist yet — this is a one-time setup step, deterministic and fast).
- **No incident appears**: confirm detection/correlation were left enabled
  when starting the run; a purely telemetry-only run has nothing to
  correlate.
- **Workflow does not start after replay**: confirm Autonomous mode was enabled
  before launch, or use **Run Blue workflow** on Command Centre.
- **Backend unreachable**: confirm `docker compose ps` shows the backend
  healthy, or re-run `python -m alembic upgrade head` if using the direct
  local setup — a missing migration is the most common local-setup cause.
- If genuinely stuck, refresh the browser tab; state is persisted
  server-side per run, so a reload does not lose the demo's evidence.

## Verified boundary

The Windows production launcher, isolated model/database bootstrap, `/app`,
backend health and safety endpoints, and shutdown were re-verified on
2026-10-19. Docker and Azure are optional deployment paths, not prerequisites
for this local faculty demonstration. CICIDS2017 is not part of this synthetic
walkthrough and no real-data result should be claimed unless the official
corpus has been separately supplied and measured.
