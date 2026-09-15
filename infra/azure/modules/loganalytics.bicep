// AegisArena — Log Analytics workspace backing the Container Apps environment.
// PerGB2018 (pay-as-you-go) SKU with the lowest reasonable retention (30 days)
// to keep this a low-cost dev environment.

@description('Azure region for the workspace.')
param location string

@description('Log Analytics workspace name.')
param workspaceName string = 'log-aegisarena-dev'

@description('Data retention in days (lowest reasonable default for a dev environment).')
param retentionInDays int = 30

resource workspace 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: workspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: retentionInDays
  }
}

output workspaceId string = workspace.id
output workspaceName string = workspace.name
