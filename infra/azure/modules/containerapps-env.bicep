// AegisArena — Container Apps Environment, Consumption workload profile only.
//
// No `workloadProfiles` array is set on purpose: omitting it entirely keeps
// the environment on the default Consumption plan (no dedicated/premium
// workload profiles), which is what the PM's low-cost scope calls for.

@description('Azure region for the environment.')
param location string

@description('Container Apps Environment name.')
param environmentName string = 'cae-aegisarena-dev'

@description('Name of the Log Analytics workspace to attach for app logs.')
param logAnalyticsWorkspaceName string

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2025-02-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    // No workloadProfiles -> Consumption-only environment (PM scope).
  }
}

output environmentId string = containerAppsEnvironment.id
output environmentName string = containerAppsEnvironment.name
