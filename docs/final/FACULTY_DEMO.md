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
see `frontend/src/components/simulation/RedAgentPanel.tsx`). Recommended
seed: `84`. Recommended playback speed: `50×` so the run completes in well
under a minute of real time instead of requiring the presenter to wait.

## Exact screen flow

1. **Command Centre (`/`)** — Start here. Point out the current cloud
   posture (Cloud Health, Risk Score, Availability, Active Incidents), the
   embedded Digital Twin preview, and the empty Resilience/Activity panels
   *before* starting anything — this is the system's honest "nothing has
   happened yet" state.
2. In the **Red Agent** control rail (bottom-left of Command Centre), select
   `staged-compromise-demo`, seed `84`, speed `50×`, leave detection/
   correlation/prediction enabled, and click **Start**.
3. Watch the **Recent Activity** timeline populate in real time: scenario
   started → anomaly detected → incident created → response proposed →
   verification completed. Narrate each step as it appears.
4. Once an incident exists, open **Digital Twin (`/digital-twin`)**. Show
   the topology view, then the **Attack Paths** and **Blast Radius** tabs —
   this is where to say "the system is reasoning about the graph, not
   guessing from a severity table."
5. Open **Threat Analysis → Incidents** and **MITRE ATT&CK** to show the
   correlated incident, its priority/evidence, and the mapped ATT&CK
   techniques.
6. Open **Defense → Agent Workflow (`/blue-agent/agent-workflow`)** and
   select the current orchestration from the "Live agent trace" dropdown.
   This is the strongest research-facing screen: it shows every one of the
   six Blue agents' decisions in order — Response Planner, Impact
   Simulation, Safety Governor, Approval Router, Synthetic Execution,
   Verification — each with its rationale and any warnings. Say: *"this is
   not a black box; every decision here is deterministic and auditable."*
7. Back on **Command Centre**, point out the now-populated **Blue Agent
   Recommendation** card (Defense Score, security improvement vs.
   availability/SLA cost, approval tier) and the **Resilience** card
   (Aegis Resilience Score / Mission Continuity Index, if at least one
   Evaluation experiment has already been run — see step 8).
8. Open **Evaluation (`/evaluation`)**. If experiments already exist from a
   prior session, show the Overview (mean ARS, mean MCI, verified
   containment rate across defence modes) then drill into **Experiments**
   and one **Compare** view contrasting `AGENTIC` against
   `NO_ACTIVE_DEFENCE`. If none exist yet, create one experiment live using
   the same scenario/seed to show the pipeline end-to-end producing a
   scored result — do **not** run the full 80-experiment canonical matrix
   during a demo; one experiment is enough to prove the mechanism.

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
- A completed Evaluation experiment with a numeric ARS (0–100) and MCI.

## Recovery if a step fails

- **Scenario won't start**: check a detection model exists (Model Analytics
  page → "Create one in Detection Models" link on the Red Agent panel if
  none exist yet — this is a one-time setup step, deterministic and fast).
- **No incident appears**: confirm detection/correlation were left enabled
  when starting the run; a purely telemetry-only run has nothing to
  correlate.
- **Blue Agent card stays empty**: click "Rank mitigations" manually — this
  triggers on-demand rather than automatically in some playback states.
- **Backend unreachable**: confirm `docker compose ps` shows the backend
  healthy, or re-run `python -m alembic upgrade head` if using the direct
  local setup — a missing migration is the most common local-setup cause.
- If genuinely stuck, refresh the browser tab; state is persisted
  server-side per run, so a reload does not lose the demo's evidence.
