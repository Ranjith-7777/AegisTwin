# AegisArena — Azure infrastructure (Bicep)

Low-cost Azure dev deployment for AegisArena, scoped and approved by the
Project Manager. This is infrastructure-as-code only: nothing here has been
deployed, and this README does not authorize running `az` against a live
subscription.

## Layout

```
infra/azure/main.bicep                    subscription-scope orchestrator
infra/azure/modules/identity.bicep        id-aegisarena-app, id-aegisarena-github
infra/azure/modules/acr.bicep             acraegisarenadev<suffix> (Basic, admin disabled)
infra/azure/modules/keyvault.bicep        kv-aegisarena-dev (RBAC-authorized)
infra/azure/modules/loganalytics.bicep    log-aegisarena-dev (PerGB2018, 30d retention)
infra/azure/modules/containerapps-env.bicep  cae-aegisarena-dev (Consumption only)
infra/azure/modules/containerapp.bicep    ca-aegisarena-dev (frontend + backend sidecars)
infra/azure/modules/postgres.bicep        psql-aegisarena-dev<suffix> (Burstable B1ms)
infra/azure/parameters/dev.bicepparam     non-secret dev parameters
```

## Scope choice: subscription-scope `main.bicep`

`main.bicep` sets `targetScope = 'subscription'`. It creates the
`rg-aegisarena-dev` resource group itself, then deploys every module into
that resource group with `scope: resourceGroup(rg.name)`. This means the
whole environment can be stood up with a single command:

```
az deployment sub create \
  --location centralindia \
  --template-file infra/azure/main.bicep \
  --parameters infra/azure/parameters/dev.bicepparam
```

A resource-group-scoped `main.bicep` (with the calling workflow running
`az group create` first) would be an equally valid alternative — it was not
chosen here because it would split "create the RG" and "populate the RG"
across two files/steps for no benefit in this project's CI shape.

## Idempotency

No non-deterministic Bicep functions (`utcNow()`, etc.) are used anywhere.
Every generated name (`acraegisarenadev<suffix>`, `psql-aegisarena-dev<suffix>`)
uses `uniqueString(resourceGroup().id)`, which is a pure function of the
resource group's resource ID — re-running the same deployment produces the
same names and updates resources in place rather than creating duplicates.

## GitHub Actions OIDC: manual federated-credential step (NOT in Bicep)

`modules/identity.bicep` creates `id-aegisarena-github` but deliberately does
**not** create a `federatedIdentityCredentials` child resource for it.
Federated credentials need the consuming GitHub org/repo and branch (or
environment) name and the exact subject claim format — CI configuration, not
general infra — so wire it up once, after this Bicep has been deployed, with:

```
az identity federated-credential create \
  --name gha-federated-credential \
  --identity-name id-aegisarena-github \
  --resource-group rg-aegisarena-dev \
  --issuer https://token.actions.githubusercontent.com \
  --subject repo:<org>/<repo>:ref:refs/heads/main \
  --audiences api://AzureADTokenExchange
```

Adjust `--subject` if the workflow should trigger from a different branch,
a tag, a pull request, or a GitHub Environment (see Microsoft's OIDC subject
claim docs for the exact string per trigger type). After this, configure the
GitHub Actions `azure/login` step with:
- `client-id`: the `githubIdentityClientId` output of `main.bicep`
- `tenant-id`: the Azure AD tenant ID
- `subscription-id`: the target subscription ID
- no client secret — OIDC replaces it entirely.

## Role assignments (least privilege)

| Identity                 | Role                 | Scope                       | Role definition GUID                    |
|---------------------------|----------------------|------------------------------|------------------------------------------|
| id-aegisarena-app          | AcrPull              | acraegisarenadev<suffix>     | `7f951dda-4ed3-4680-a7ca-43fe172d538d`   |
| id-aegisarena-app          | Key Vault Secrets User | kv-aegisarena-dev          | `4633458b-17de-408a-b874-0445c86b69e6`   |
| id-aegisarena-github       | AcrPush              | acraegisarenadev<suffix>     | `8311e382-0749-4cb8-b61a-304f252e45ec`   |
| id-aegisarena-github       | Contributor          | rg-aegisarena-dev (RG only)  | `b24988ac-6180-42a0-ab88-20f7382dd24c`   |

`id-aegisarena-github` intentionally never gets subscription-level Owner or
Contributor — its Contributor grant is scoped to `rg-aegisarena-dev` alone,
because the only role assignment resource for it is deployed inside
`modules/identity.bicep`, which itself is deployed at that resource group's
scope with no explicit wider `scope:` override.

## Postgres network tradeoff

Container Apps Consumption workload profile does not support VNet
integration / private endpoints in the same low-cost way a dedicated/premium
workload profile would. `modules/postgres.bicep` therefore uses:
- Public network access, restricted to the standard "Allow public access
  from any Azure service within Azure to this server" firewall rule
  (`0.0.0.0`–`0.0.0.0`) — this opens the server to Azure's own service
  backbone, not the public internet.
- `require_secure_transport = ON`, enforcing TLS on every connection
  regardless of network path.

A private-endpoint/VNet-integrated design would cost more and add
disproportionate complexity for this project's scope; it is a documented
Phase 7+ hardening opportunity if the project ever needs it.

## Secrets handling

- The Postgres admin password is a `@secure()` parameter with **no default**
  anywhere. `parameters/dev.bicepparam` reads it from the `PGADMIN_PASSWORD`
  environment variable via `readEnvironmentVariable(...)` — never hardcode it
  or commit a value for it.
- `modules/postgres.bicep` writes the resulting `postgresql+psycopg://...`
  connection string directly into the `database-url` secret in
  `kv-aegisarena-dev`. It is never emitted as a plain Bicep output.
- The Container App reads that secret at revision start via Container Apps'
  native Key Vault secret reference (`secrets[].keyVaultUrl` +
  `identity: appIdentityId`), exposing it to the `backend` container only as
  `DATABASE_URL` through `secretRef`.

## Validation performed

- **`bicep build` / `az bicep build`: NOT run.** Neither the Bicep CLI nor
  the Azure CLI is installed in this environment (`bicep --version` and
  `az --version` both fail with "command not found" in both the bash and
  PowerShell shells checked). This is a manual-review-only validation pass.
- Every resource type and API version was cross-checked against the Azure
  MCP `bicepschema` tool's live schema lookup (not guessed):
  - `Microsoft.App/containerApps@2025-01-01`
  - `Microsoft.App/managedEnvironments@2025-01-01`
  - `Microsoft.KeyVault/vaults@2024-11-01` (and its `secrets` child)
  - `Microsoft.ContainerRegistry/registries@2025-04-01`
  - `Microsoft.OperationalInsights/workspaces@2025-02-01`
  - `Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30`
  - `Microsoft.Authorization/roleAssignments@2022-04-01`
  - `Microsoft.Resources/resourceGroups@2021-04-01` (well-known stable
    version; not schema-checked via the MCP tool, which only covers
    resource-group-and-deeper scopes)
- `Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01` (and its
  `databases`, `firewallRules`, `configurations` children): the schema tool's
  full schema lookup for this resource type returned an error ("apiVersion
  2024-08-01 not supported" by the tool's local schema cache), but the error
  message itself confirms `2024-08-01` as the version the tool identifies as
  current/latest for this resource type — it is a real, current API version,
  just not one the schema-fetch endpoint has cached a full property listing
  for. Property names (`administratorLogin`, `administratorLoginPassword`,
  `storage.storageSizeGB`, `highAvailability.mode`, `version`) were hand-
  verified against Microsoft's published Postgres Flexible Server Bicep
  reference rather than guessed.
- **SKU flagged for follow-up verification before first real deploy:**
  `Standard_B1ms` for `Microsoft.DBforPostgreSQL/flexibleServers` — this is
  the smallest practical Burstable tier and was not independently listed by
  the MCP tool (its schema fetch failed as above). Confirm regional
  availability with `az postgres flexible-server list-skus --location
  centralindia` before the first actual deployment.
- Every `.bicep` file was manually checked for matching braces/brackets,
  correctly declared `@secure()`/`@description()` decorators, correct
  `parent`/`scope` usage on child and extension resources, and consistent
  module-to-module parameter wiring (no unresolved references).
