// AegisArena — Key Vault (RBAC-authorized, standard SKU).
//
// enableRbacAuthorization: true — no access-policy list to maintain; grants
// are plain role assignments, consistent with the rest of this template.

@description('Azure region for the vault.')
param location string

@description('Key Vault name. "kv-aegisarena-dev" is 17 characters, well within the 3-24 character global-uniqueness limit, so — per the PM-approved naming — it is used as-is with no generated suffix.')
param keyVaultName string = 'kv-aegisarena-dev'

@description('principalId of id-aegisarena-app — granted Key Vault Secrets User, scoped to this vault only.')
param appIdentityPrincipalId string

// Built-in role definition GUID: Key Vault Secrets User. Stable across all tenants.
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

resource vault 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
  }
}

resource kvSecretsUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, appIdentityPrincipalId, keyVaultSecretsUserRoleId)
  scope: vault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: appIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output keyVaultId string = vault.id
output keyVaultName string = vault.name
output keyVaultUri string = vault.properties.vaultUri
