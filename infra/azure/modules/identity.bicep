// AegisArena — user-assigned managed identities.
//
// Creates the two identities the PM's approved design calls for:
//   - id-aegisarena-app     : Container App runtime identity (ACR pulls, Key Vault reads).
//   - id-aegisarena-github  : GitHub Actions OIDC deployment identity (CI pushes images,
//                             runs `az deployment` against this resource group).
//
// NOTE ON FEDERATED CREDENTIALS: this module deliberately does NOT create a
// `Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials`
// child resource for id-aegisarena-github. Wiring GitHub OIDC requires the
// consuming GitHub repo/org and the EXACT subject claim GitHub emits for
// this repository's workflow — details that belong to the CI setup, not to
// this general-purpose infra template, and that must be verified against
// the real repository rather than assumed. .github/workflows/deploy-azure.yml
// runs its deploy job under GitHub Environment `production`, so this needs
// an environment-context subject, not a branch-ref subject — and some
// repositories/orgs use GitHub's newer immutable, ID-based OIDC subject
// format instead of the classic name-based one. See
// infra/azure/README.md and docs/deployment/AZURE_DEPLOYMENT.md for the
// full walkthrough, including how to verify the actual subject before
// creating anything here. No federated credential has been created.

@description('Azure region for both identities.')
param location string

@description('Name of the Container App runtime managed identity.')
param appIdentityName string = 'id-aegisarena-app'

@description('Name of the GitHub Actions OIDC deployment managed identity.')
param githubIdentityName string = 'id-aegisarena-github'

// Built-in role definition GUID: Contributor. Stable across all tenants.
var contributorRoleId = 'b24988ac-6180-42a0-ab88-20f7382dd24c'

resource appIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: appIdentityName
  location: location
}

resource githubIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: githubIdentityName
  location: location
}

// Least-privilege for CI: Contributor scoped to ONLY this resource group (the
// implicit scope of this module's deployment — it is deployed with
// `scope: resourceGroup(rg.name)` from main.bicep), never subscription-wide
// Owner/Contributor.
resource githubContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, githubIdentity.id, contributorRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', contributorRoleId)
    principalId: githubIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output appIdentityId string = appIdentity.id
output appIdentityPrincipalId string = appIdentity.properties.principalId
output appIdentityClientId string = appIdentity.properties.clientId
output githubIdentityId string = githubIdentity.id
output githubIdentityPrincipalId string = githubIdentity.properties.principalId
output githubIdentityClientId string = githubIdentity.properties.clientId
