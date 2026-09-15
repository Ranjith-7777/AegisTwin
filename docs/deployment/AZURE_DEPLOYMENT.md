# Azure Deployment

This document is the procedural guide for deploying AegisArena to Azure. See
`docs/deployment/AZURE_ARCHITECTURE.md` for what gets deployed and why. As of
writing, nothing described here has been deployed yet — this documents how
the deployment is intended to work.

## Prerequisites

- Azure subscription with permission to create resource groups, managed
  identities, and role assignments (owner/contributor at subscription scope,
  for the one-time bootstrap only — day-to-day deploys use the
  RG-scoped `id-aegisarena-github` identity instead).
- Azure CLI (`az`) installed locally for the one-time bootstrap steps below.
- Repository admin access on GitHub, to set repository/environment
  variables and secrets and to create the `production` Environment.

## One-time setup

### 1. Provision the two managed identities and their federated credentials

`infra/azure/main.bicep` creates the two user-assigned managed identities
(`id-aegisarena-app`, `id-aegisarena-github`) themselves, but it intentionally
**does not** create the GitHub OIDC federated credential on
`id-aegisarena-github` — that binding names a specific GitHub repository and
branch/environment, which is an operator decision, not infrastructure that
should be silently re-created by every `bicep deploy`. Create it manually,
once, after the identity exists:

```bash
az identity federated-credential create \
  --name "github-oidc-deploy" \
  --identity-name "id-aegisarena-github" \
  --resource-group "rg-aegisarena-dev" \
  --issuer "https://token.actions.githubusercontent.com" \
  --subject "repo:<GITHUB_ORG>/<GITHUB_REPO>:environment:production" \
  --audiences "api://AzureADTokenExchange"
```

Replace `<GITHUB_ORG>/<GITHUB_REPO>` with this repository's org/name. The
`subject` above scopes the federated credential to the `production`
GitHub Environment specifically (matching `environment: production` in
`.github/workflows/deploy-azure.yml`). If you additionally want the
`push` trigger on `develop` to work without going through the Environment,
add a second federated credential with
`--subject "repo:<GITHUB_ORG>/<GITHUB_REPO>:ref:refs/heads/develop"`.

### 2. Validate the Bicep template with what-if before applying

Always preview changes before applying them, especially against a live
environment:

```bash
az deployment sub what-if \
  --location centralindia \
  --template-file infra/azure/main.bicep \
  --parameters infra/azure/parameters/dev.bicepparam
```

(`--location` here only names where the deployment *record* is stored, not
where resources land — that's controlled by the `location` param inside the
template, which already defaults to `centralindia`. Kept aligned to avoid
confusion when reading deployment history later.)

Review the plan output for unexpected deletions/replacements before running
an actual deployment (via the workflow below, or `az deployment sub create`
directly for a manual one-off).

### 3. Set GitHub repository variables (non-secret identifiers)

Settings → Secrets and variables → Actions → Variables:

| Variable | Value |
|---|---|
| `AZURE_CLIENT_ID` | Client (application) ID of `id-aegisarena-github` |
| `AZURE_TENANT_ID` | Entra tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Target subscription ID |
| `ACR_NAME` | The **actual deployed** registry name — read it from the first `az deployment sub create`/`what-if` run's `acrLoginServer` output (it is `acraegisarenadev` plus a short generated suffix, e.g. `acraegisarenadevab12`, stripped of the trailing `.azurecr.io`), not the bare `acraegisarenadev` base name |

These are identifiers, not credentials — there is no secret material in any
of them, which is why they are GitHub *variables* rather than *secrets*
(and why `deploy-azure.yml` reads them via `vars.*`).

### 4. Set the one GitHub secret that is genuinely sensitive

Settings → Secrets and variables → Actions → Secrets:

| Secret | Value |
|---|---|
| `PGADMIN_PASSWORD` | Postgres Flexible Server admin password |

This is used only at first deploy, to create the Postgres admin account and
write the resulting connection string into Key Vault. Because Bicep is
idempotent about the server itself, subsequent deploys do not need to (and
should not) rotate this value — see the inline comment in
`.github/workflows/deploy-azure.yml`'s deploy step.

### 5. Create the GitHub `production` Environment (manual, one-time)

This cannot be done from a workflow file — it is a GitHub repository
settings action:

1. Settings → Environments → New environment → name it `production`.
2. Add a required reviewer (or other protection rule) if you want manual
   approval before `deploy-azure.yml`'s `deploy` job runs.
3. Environment-scoped variables/secrets can also be set here instead of at
   the repository level if you want the `production` Environment to be the
   only place these values live.

## Running a deployment

`deploy-azure.yml` is manual-first by design (cost safety on a student
subscription): trigger it via **Actions → Deploy Azure → Run workflow**,
optionally supplying an `image_tag` (defaults to the triggering commit SHA
if left blank). It will:

1. Authenticate to Azure via OIDC (no stored secret).
2. `az acr login` and build+push the backend and frontend images, tagged
   both with the immutable SHA and `:latest` (SHA tag is what actually gets
   deployed).
3. Run `az deployment sub create` against `infra/azure/main.bicep` and
   `infra/azure/parameters/dev.bicepparam`, overriding `imageTag`.
4. Poll `/api/health/live` and `/api/health/ready` on the resulting
   Container App FQDN, retrying for cold starts, and fail the job if either
   check does not return 200 within the retry budget.

A push to the `develop` branch also triggers this workflow (per the PM's
brief that deploys should follow "approved changes to develop"), gated so
it never fires for any other branch or for pull requests.
