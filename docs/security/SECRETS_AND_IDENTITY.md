# Secrets and Identity

This document describes where secrets live and which managed identity is
responsible for what, in the Azure deployment described in
`docs/deployment/AZURE_ARCHITECTURE.md`.

## What is stored where

| Item | Stored in | Accessed by |
|---|---|---|
| Postgres connection string | Azure Key Vault, as a secret | Container App, via a native Key Vault secret reference resolved using the `id-aegisarena-app` managed identity — the value is injected as an environment variable at container start and is never written into the image, the workflow YAML, or source control. |
| Postgres admin password (first deploy only) | GitHub Actions secret `PGADMIN_PASSWORD` | `deploy-azure.yml`'s Bicep deployment step only, at Postgres server-creation time; the same value is then written into Key Vault as the connection string component. It is not stored anywhere else and is not re-used by the application at runtime (the app reads the Key Vault-resolved connection string, not this secret directly). |
| Container images | Azure Container Registry (`${{ vars.ACR_NAME }}`) | Pulled by the Container App via `id-aegisarena-app`'s `AcrPull` role assignment; pushed by CI via `id-aegisarena-github`'s `AcrPush` role assignment. |
| GitHub OIDC deploy credential | Nothing stored — workload identity federation issues short-lived tokens per workflow run | `id-aegisarena-github`, via a federated credential trust relationship (see `docs/deployment/AZURE_DEPLOYMENT.md`), no client secret exists to leak. |

**No secret value is ever committed to git, baked into a container image, or
written into workflow YAML**, with the single documented exception of
`PGADMIN_PASSWORD` living in GitHub's encrypted Actions secrets store (which
is the correct, intended place for a genuine secret — see
`.github/workflows/deploy-azure.yml`'s inline comments).

## Two managed identities, two distinct responsibilities

Per a least-privilege design, the application runtime and the CI/CD
deployment pipeline use **separate** identities, each scoped to only what it
needs:

### `id-aegisarena-app` — application runtime identity

Used by the running Container App at request-serving time. Role
assignments (from the Bicep definition):

- `AcrPull` on the registry — so the Container App can pull its own images.
- `Key Vault Secrets User` on the vault — so it can resolve the Postgres
  connection string secret reference at container start.

It has no write access to the registry, no access to the resource group's
control plane, and no broader subscription-level permissions.

### `id-aegisarena-github` — CI/CD deploy identity

Used exclusively by `.github/workflows/deploy-azure.yml`, authenticated via
GitHub OIDC federation (see ADR-017). Role assignments:

- `AcrPush` on the registry — so CI can publish new image tags.
- `Contributor`, **scoped to the resource group** `rg-aegisarena-dev` only
  (not the subscription) — so CI can run `az deployment sub create` /
  update the Container App, Key Vault secret, and other resources inside
  that group, but cannot touch anything outside it.

Neither identity can act on the other's behalf, and neither has standing
access broader than the single resource group / single registry this
project owns.
