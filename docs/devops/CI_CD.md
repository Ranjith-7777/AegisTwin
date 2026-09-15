# CI/CD

## Continuous Integration

Four workflows run under `.github/workflows/`:

| Workflow | Trigger | Purpose |
|---|---|---|
| `backend-ci.yml` | push, pull_request | Ruff lint/format, mypy, pytest for `backend/`. |
| `frontend-ci.yml` | push, pull_request | ESLint, format check, typecheck, unit tests, build for `frontend/`. |
| `release-validation.yml` | push, pull_request | Broader gate: backend/frontend quality checks again, a clean-database migration check (`alembic upgrade head` against a fresh SQLite file), and a deterministic end-to-end Playwright run plus `scripts/final_benchmark.py`, with evidence uploaded as a build artifact. |
| `docker-build-validate.yml` (new in Phase 6) | push, pull_request | Builds (does not push) `backend/Dockerfile` and `frontend/Dockerfile` via `docker/build-push-action` with `push: false`, using GitHub Actions cache (`type=gha`) to keep it fast. Pure CI hygiene — catches Dockerfile breakage early, makes no Azure calls, needs no credentials. |

These run on every push/PR to any branch; none of them touch Azure or
require any cloud credentials.

## Continuous Deployment

`deploy-azure.yml` (new in Phase 6) is the one workflow that touches real
Azure resources. It is **manual-only**:

- Only trigger: `workflow_dispatch`, with an optional `image_tag` input
  (defaults to the triggering commit SHA). There is no `push` trigger of any
  kind — the user explicitly wants to control Azure spending by hand, so no
  deployment happens without someone explicitly clicking "Run workflow." An
  earlier draft of this workflow included a secondary `push`-to-`develop`
  trigger; it was removed for this reason.
- It is for **post-bootstrap deployments only**. A brand-new environment's
  first-ever deployment is a manual, human-run two-pass process (PASS 1
  creates supporting infrastructure without the Container App; images are
  built/pushed; PASS 2 creates the Container App) — see
  `docs/deployment/AZURE_DEPLOYMENT.md` and `infra/azure/README.md`'s
  "Two-pass bootstrap" section. `deploy-azure.yml` cannot perform that first
  deployment (the identity it authenticates as does not exist until
  bootstrap has run), and it explicitly **preflight-checks** that
  `rg-aegisarena-dev` and the configured ACR already exist before doing
  anything else, failing with a message pointing back to
  `AZURE_DEPLOYMENT.md` if they don't.

It authenticates to Azure via **OIDC workload identity federation**
(`azure/login@v2` with `client-id`/`tenant-id`/`subscription-id` read from
GitHub repository **variables**, not secrets — see
`docs/deployment/AZURE_DEPLOYMENT.md` and ADR-017) — there is no long-lived
Azure credential stored in GitHub at all. After the preflight check passes,
it builds and pushes both container images, then runs
`az deployment group create --resource-group rg-aegisarena-dev` against
**`infra/azure/app.bicep`** — deliberately **not** the subscription-scope
`infra/azure/main.bicep` used for bootstrap. This matters for least
privilege: `id-aegisarena-github` holds only RG-scoped `Contributor` on
`rg-aegisarena-dev` (see `infra/azure/README.md`'s role table), which is
incapable of running a subscription-scope deployment at all — `app.bicep`
only ever updates the existing Container App, referencing the
already-bootstrapped ACR/Key Vault/Container Apps Environment/identity as
`existing` resources, so that RG-scoped privilege is exactly sufficient.
No `PGADMIN_PASSWORD` or any secret is required for this step — `app.bicep`
never touches PostgreSQL. `trustEasyAuthHeaders` stays at its Bicep default
`false` in this workflow (see `docs/deployment/AZURE_DEPLOYMENT.md`'s
"Enabling `trustEasyAuthHeaders=true`" section for how an operator supplies
`true` explicitly on a manual run, once Easy Auth has been verified). The
job gates success on `/api/health/live` and `/api/health/ready` responding,
with retries to absorb Container Apps scale-from-zero cold starts.

Full deployment procedure: `docs/deployment/AZURE_DEPLOYMENT.md`.
Architecture it deploys: `docs/deployment/AZURE_ARCHITECTURE.md`.

## Manual one-time step: the `production` GitHub Environment

`deploy-azure.yml`'s `deploy` job specifies `environment: production`. This
lets GitHub's **Environment protection rules** (e.g. a required reviewer who
must approve before the job runs) gate real Azure deployments, on top of the
branch/trigger gate already in the workflow file itself.

**Creating the Environment and adding a required reviewer cannot be done
from a workflow file or any other file in this repository — it is a
one-time manual action in the GitHub web UI:**

1. Repository → **Settings → Environments → New environment**.
2. Name it exactly `production` (must match `environment: production` in
   `deploy-azure.yml`).
3. Under **Deployment protection rules**, add a required reviewer (and/or
   a wait timer, restricted branches, etc., as desired).
4. Optionally, move `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` /
   `AZURE_SUBSCRIPTION_ID` / `ACR_NAME` (variables) to be Environment-scoped
   instead of repository-scoped, if you want them to only be readable within
   this specific protected Environment. There is no `PGADMIN_PASSWORD` (or
   any other secret) for this workflow to move — normal releases via
   `app.bicep` never need the Postgres admin password at all; see
   `docs/deployment/AZURE_DEPLOYMENT.md`.

**This was not verified against this repository's live GitHub settings** —
doing so would require `gh` calls against the live repo, which this task
was explicitly scoped to avoid. Whether the repository's current GitHub
plan supports Environment protection rules (this is a paid-plan feature on
private repositories, unrestricted on public ones) was not checked here;
confirm it directly in the Settings UI before relying on it as an approval
gate.
