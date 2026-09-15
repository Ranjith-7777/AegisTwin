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
// consuming GitHub repo/org, branch (or environment) name, and subject claim
// format up front — details that belong to the CI setup, not to this
// general-purpose infra template. Create it once, after this Bicep has run,
// with (see infra/azure/README.md for the full walkthrough):
//
//   az identity federated-credential create \
//     --name gha-federated-credential \
//     --identity-name id-aegisarena-github \
//     --resource-group rg-aegisarena-dev \
//     --issuer https://token.actions.githubusercontent.com \
//     --subject repo:<org>/<repo>:ref:refs/heads/main \
//     --audiences api://AzureADTokenExchange

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
