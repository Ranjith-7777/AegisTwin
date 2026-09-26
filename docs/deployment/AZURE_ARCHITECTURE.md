# Azure Architecture

This document describes the approved Phase 6 deployment architecture for
AegisArena on Azure. Nothing described here has been deployed yet as of
writing — this document specifies the target architecture that
`infra/azure/main.bicep` provisions and `.github/workflows/deploy-azure.yml`
deploys to.

## Overview

AegisArena remains a single-process, in-process-stateful application (see
`docs/DEPLOYMENT_REQUIREMENTS.md` and ADR-013's discussion of the
application's process-local event bus and simulation state). The Azure
architecture is deliberately the simplest shape that hosts that application
reliably and cheaply, rather than a general-purpose scaled platform.

```
                         ┌─────────────────────────────┐
                         │   Container Apps Environment │
                         │                              │
  Internet ── HTTPS ───▶ │  ┌────────────────────────┐  │
  (ingress)              │  │   Container App          │  │
                         │  │   ca-aegisarena-dev      │  │
                         │  │                          │  │
                         │  │  ┌────────┐  ┌─────────┐ │  │
                         │  │  │frontend│─▶│ backend │ │  │
                         │  │  │ nginx  │  │ FastAPI │ │  │
                         │  │  │:8080   │  │ :8000   │ │  │
                         │  │  └────────┘  └────┬────┘ │  │
                         │  │  (same replica,     │      │  │
                         │  │   shared network ns) │      │  │
                         │  └───────────────────────┼──────┘  │
                         │        min=0 max=1        │         │
                         └────────────────────────────┼─────────┘
                                                       │
                          ┌────────────────────────────┼───────────────┐
                          │                             │               │
                          ▼                             ▼               ▼
                 ┌─────────────────┐          ┌──────────────────┐  ┌───────────────┐
                 │ Azure Container │          │ Postgres Flexible │  │  Key Vault    │
                 │ Registry (ACR)  │          │ Server (B1ms,      │  │ (conn string, │
                 │ acraegisarenaXX │          │ no HA)             │  │  secrets)     │
                 └─────────────────┘          └──────────────────┘  └───────────────┘

                          ┌────────────────────────────┐
                          │      Log Analytics          │
                          │  (Container Apps + app logs,│
                          │   30-day retention)          │
                          └────────────────────────────┘

     Managed identities:
       id-aegisarena-app     -> AcrPull, Key Vault Secrets User (runtime identity)
       id-aegisarena-github  -> AcrPush, RG-scoped Contributor  (CI/CD deploy identity)
```

## Components

- **Container App (`ca-aegisarena-dev`)** — runs the frontend (nginx) and
  backend (FastAPI/uvicorn) as two containers ("sidecars") inside the same
  Container App revision, sharing a network namespace. The frontend
  container terminates public HTTP(S) traffic and reverse-proxies `/api` and
  `/ws` to the backend container over `localhost` — see
  `frontend/nginx.conf.template` and `frontend/Dockerfile`.
- **Container Apps Environment** — the managed hosting boundary (VNet
  integration point, shared Log Analytics workspace) that the Container App
  runs inside.
- **Azure Container Registry (`${{ vars.ACR_NAME }}`, e.g.
  `acraegisarenadev` with a deterministic suffix)** — Basic tier, stores the
  `aegisarena/frontend` and `aegisarena/backend` images tagged by git SHA.
- **Azure Database for PostgreSQL — Flexible Server** — Burstable B1ms, no
  high availability. Replaces SQLite in this environment; see
  ADR-015 for the rationale.
- **Key Vault** — holds the Postgres connection string, referenced by the
  Container App via a native Key Vault secret reference (no secret value is
  baked into the image or workflow YAML). See
  `docs/security/SECRETS_AND_IDENTITY.md`.
- **Two user-assigned managed identities**:
  - `id-aegisarena-app` — the application runtime identity. Least-privilege:
    `AcrPull` on the registry and `Key Vault Secrets User` on the vault.
    Nothing else.
  - `id-aegisarena-github` — the CI/CD deploy identity, federated with
    GitHub OIDC (no stored secret). Least-privilege: `AcrPush` on the
    registry and `Contributor` scoped to the resource group only (not the
    subscription). See ADR-017.
- **Log Analytics workspace** — collects Container Apps system logs and
  application stdout/stderr, retained 30 days (see
  `docs/deployment/COST_CONTROL.md`).

## Scaling: `maxReplicas=1` is intentional

The Container App is configured with `minReplicas=0` and `maxReplicas=1`.
The upper bound is **not** a temporary limitation to be "fixed" later — it
is a direct consequence of the application's architecture, matching
`backend/Dockerfile`'s single-uvicorn-worker rationale and
`docs/DEPLOYMENT_REQUIREMENTS.md`:

- The event bus (`InProcessEventBus`) and the digital twin simulation state
  are held in Python process memory, not in an external store.
- Running more than one replica (or more than one worker process within a
  replica) would create independent, diverging copies of that state —
  requests routed to different replicas would see inconsistent simulation
  state, breaking correctness, not just performance.

**Phase 6 explicitly does not introduce Redis, Kafka, Dapr, or any other
externalized-state/message-broker component to work around this.**
Generalizing the runtime to support horizontal scaling would require
redesigning the event bus and simulation state to be shared/external, which
is out of scope for this phase and is tracked as a known architectural
limitation, not a defect to be silently patched via new infrastructure.
`minReplicas=0` (scale-to-zero when idle) is what keeps this affordable; see
`docs/deployment/COST_CONTROL.md` for the demo scale-up procedure.

## Related documents

- `docs/deployment/AZURE_DEPLOYMENT.md` — how to deploy this architecture.
- `docs/deployment/COST_CONTROL.md` — steady-state cost posture and
  temporary scale-up/down for demos.
- `docs/deployment/ROLLBACK.md` — revision-based rollback procedure.
- `docs/security/SECRETS_AND_IDENTITY.md` — what's stored where and by
  which identity.
- `docs/security/AUTHENTICATION.md` — the Easy Auth trust boundary this
  architecture relies on.
- ADR-014, ADR-015, ADR-016, ADR-017 in `docs/architecture/adr/` — the
  decisions behind this shape.
