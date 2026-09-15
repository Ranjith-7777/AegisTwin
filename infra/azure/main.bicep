// AegisArena — low-cost Azure dev deployment (Phase 6, PM-approved scope).
//
// SCOPE CHOICE: this orchestrator runs at SUBSCRIPTION scope
// (`targetScope = 'subscription'`) so a single `az deployment sub create`
// call both creates the `rg-aegisarena-dev` resource group AND deploys every
// child resource into it via modules scoped to that resource group. The
// alternative — a resource-group-scoped main.bicep paired with a separate
// `az group create` step upstream in the calling workflow — is an equally
// valid pattern, but subscription scope keeps the whole environment
// reproducible from one command and one entry-point file, which is simpler
// for a CI workflow (or a human) to invoke without an extra bootstrap step.
//
// No non-deterministic functions (utcNow(), etc.) are used anywhere in this
// template or its modules — every generated name is a pure function of
// resourceGroup().id via uniqueString(), so re-running this deployment is
// idempotent.
targetScope = 'subscription'

@description('Azure region for every resource.')
param location string = 'centralindia'

@description('Name of the resource group this deployment creates and populates.')
param resourceGroupName string = 'rg-aegisarena-dev'

@description('Immutable image tag (e.g. a git SHA) applied to both the frontend and backend containers. "latest" is a placeholder for local iteration only — real deployments MUST override this with an immutable tag.')
param imageTag string = 'latest'

@description('Minimum Container App replicas (0 = scale to zero when idle, for near-zero cost between demos).')
param minReplicas int = 0

@description('Maximum Container App replicas.')
param maxReplicas int = 1

@description('Entra/Easy-Auth principal IDs (object IDs) granted ADMIN role. Empty by default — configure explicitly per docs/security/AUTHENTICATION.md before relying on ADMIN-tier actions in a real deployment.')
param adminPrincipalIds array = []

@description('PostgreSQL Flexible Server administrator login name.')
param postgresAdministratorLogin string = 'aegisadmin'

@secure()
@description('PostgreSQL Flexible Server administrator password. No default — must be supplied at deploy time (e.g. a GitHub Actions secret) and must never be committed to the repo.')
param postgresAdministratorPassword string

resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: resourceGroupName
  location: location
}

module identity 'modules/identity.bicep' = {
  name: 'aegisarena-identity'
  scope: resourceGroup(rg.name)
  params: {
    location: location
  }
}

module logAnalytics 'modules/loganalytics.bicep' = {
  name: 'aegisarena-loganalytics'
  scope: resourceGroup(rg.name)
  params: {
    location: location
  }
}

module acr 'modules/acr.bicep' = {
  name: 'aegisarena-acr'
  scope: resourceGroup(rg.name)
  params: {
    location: location
    appIdentityPrincipalId: identity.outputs.appIdentityPrincipalId
    githubIdentityPrincipalId: identity.outputs.githubIdentityPrincipalId
  }
}

module keyVault 'modules/keyvault.bicep' = {
  name: 'aegisarena-keyvault'
  scope: resourceGroup(rg.name)
  params: {
    location: location
    appIdentityPrincipalId: identity.outputs.appIdentityPrincipalId
  }
}

module containerAppsEnvironment 'modules/containerapps-env.bicep' = {
  name: 'aegisarena-cae'
  scope: resourceGroup(rg.name)
  params: {
    location: location
    logAnalyticsWorkspaceName: logAnalytics.outputs.workspaceName
  }
}

module postgres 'modules/postgres.bicep' = {
  name: 'aegisarena-postgres'
  scope: resourceGroup(rg.name)
  params: {
    location: location
    administratorLogin: postgresAdministratorLogin
    administratorLoginPassword: postgresAdministratorPassword
    keyVaultName: keyVault.outputs.keyVaultName
  }
}

module containerApp 'modules/containerapp.bicep' = {
  name: 'aegisarena-containerapp'
  scope: resourceGroup(rg.name)
  params: {
    location: location
    containerAppsEnvironmentId: containerAppsEnvironment.outputs.environmentId
    acrLoginServer: acr.outputs.acrLoginServer
    appIdentityId: identity.outputs.appIdentityId
    keyVaultUri: keyVault.outputs.keyVaultUri
    imageTag: imageTag
    minReplicas: minReplicas
    maxReplicas: maxReplicas
    adminPrincipalIds: adminPrincipalIds
  }
  dependsOn: [
    // The Container App's Key Vault secret reference (database-url) must
    // resolve at revision start, so the secret has to exist first.
    postgres
  ]
}

// Safe outputs only — never the admin password or the connection string.
// githubIdentityPrincipalId is exposed alongside the client ID because the
// manual federated-credential + RBAC follow-up steps (see
// infra/azure/README.md) need the principal ID for verification, and the
// client ID for the GitHub Actions azure/login step configuration.
output containerAppFqdn string = containerApp.outputs.containerAppFqdn
output acrLoginServer string = acr.outputs.acrLoginServer
output keyVaultName string = keyVault.outputs.keyVaultName
output postgresServerFqdn string = postgres.outputs.postgresServerFqdn
output appIdentityClientId string = identity.outputs.appIdentityClientId
output githubIdentityClientId string = identity.outputs.githubIdentityClientId
output githubIdentityPrincipalId string = identity.outputs.githubIdentityPrincipalId
