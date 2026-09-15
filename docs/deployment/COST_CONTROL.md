# Cost Control

AegisArena's Azure footprint is sized for a student project, not production
traffic. This document lists the steady-state cost posture and the manual
scale-up/scale-down procedure for demos.

## Steady-state configuration

| Resource | Setting | Why |
|---|---|---|
| Container App (`ca-aegisarena-dev`) | `minReplicas=0`, `maxReplicas=1` | Scales to zero when idle (no compute cost between demos); capped at one replica because the app's in-process event bus and simulation state cannot be shared across replicas — see `docs/deployment/AZURE_ARCHITECTURE.md`. |
| Azure Container Registry | Basic tier | Cheapest ACR tier; sufficient for a small number of images with infrequent pushes. |
| Postgres Flexible Server | Burstable B1ms, no HA | Smallest general-purpose compute tier; no high-availability standby (which would roughly double compute cost) since this is not a production SLA workload. |
| Log Analytics workspace | 30-day retention | Keeps enough history for debugging a recent issue without paying for long-term log storage. |

Scale-to-zero means the very first request after an idle period cold-starts
a new replica (container start + `alembic upgrade head` + uvicorn boot).
`deploy-azure.yml`'s health gate accounts for this with retries; expect the
same cold-start delay on the first real user request after idle periods.

## Temporary scale-up/down for a demo

Scale-to-zero is fine for asynchronous use, but a live faculty demo should
not spend its first minute waiting on a cold start. Scale up before, back
down after:

**Before the demo** (force at least one replica to stay warm):

```bash
az containerapp update \
  --name ca-aegisarena-dev \
  --resource-group rg-aegisarena-dev \
  --min-replicas 1
```

**After the demo** (return to scale-to-zero steady state):

```bash
az containerapp update \
  --name ca-aegisarena-dev \
  --resource-group rg-aegisarena-dev \
  --min-replicas 0
```

`maxReplicas` is left at `1` in both commands — it is never raised, per the
architectural constraint described in `docs/deployment/AZURE_ARCHITECTURE.md`.

## Budget alerts — not yet confirmed

Azure Budgets (Cost Management → Budgets, with email/action-group alerts at
spend thresholds) is the standard way to get proactive notification before
a subscription overspends. **The pre-Phase-6 readiness audit did not confirm
whether Azure Budget support is available on this specific Azure for
Students subscription** (some subscription offer types have restricted
Cost Management functionality). If precise, automated budget-alert coverage
is wanted, check this manually in the Azure Portal's Cost Management blade
for the target subscription before relying on it — do not assume it is
configured or even available based on this document alone.
