// AegisArena — Azure Container Registry (Basic SKU, admin credentials disabled).
//
// Pulls/pushes are authorized purely through managed identity role
// assignments (AcrPull for the app runtime identity, AcrPush for the GitHub
// Actions deployment identity) — no admin username/password is ever enabled.

@description('Azure region for the registry.')
param location string

@description('Base name for the registry. A short deterministic suffix (uniqueString of the resource group id) is always appended to reduce the chance of colliding with the globally-unique ACR namespace, without breaking idempotent re-deployment (uniqueString is a pure function of resourceGroup().id, never of time).')
@minLength(1)
param acrBaseName string = 'acraegisarenadev'

@description('principalId of id-aegisarena-app — granted AcrPull.')
param appIdentityPrincipalId string

@description('principalId of id-aegisarena-github — granted AcrPush.')
param githubIdentityPrincipalId string

var acrName = '${acrBaseName}${take(uniqueString(resourceGroup().id), 4)}'

// Built-in role definition GUIDs. Stable across all tenants.
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var acrPushRoleId = '8311e382-0749-4cb8-b61a-304f252e45ec'

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, appIdentityPrincipalId, acrPullRoleId)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId: appIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource acrPushAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, githubIdentityPrincipalId, acrPushRoleId)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPushRoleId)
    principalId: githubIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output acrId string = registry.id
output acrName string = registry.name
output acrLoginServer string = registry.properties.loginServer
