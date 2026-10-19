// AegisArena — persistent storage for detection-model artifacts.
//
// The Container App scales to zero, so its container filesystem is
// ephemeral. Detection-model records live in PostgreSQL; their joblib
// artifacts live here, on an Azure Files share mounted at /data in the
// backend container (MODEL_ARTIFACT_DIR=/data/models). The backend also
// rebuilds a missing artifact deterministically on first use, so this share
// is an efficiency/consistency measure, not a single point of failure.
//
// Cost: Standard LRS, a 1 GiB share - pennies per month.

@description('Azure region.')
param location string

@description('Existing Container Apps Environment name the share is registered with.')
param containerAppsEnvironmentName string

@description('Storage name the Container App references (managedEnvironments/storages).')
param environmentStorageName string = 'modelartifacts'

var storageAccountName = 'staegis${uniqueString(resourceGroup().id)}'
var shareName = 'model-artifacts'

resource storageAccount 'Microsoft.Storage/storageAccounts@2024-01-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    // Azure Files SMB mounts in Container Apps authenticate with the account
    // key, so shared-key access must remain enabled for this account.
    allowSharedKeyAccess: true
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2024-01-01' = {
  parent: storageAccount
  name: 'default'
}

resource share 'Microsoft.Storage/storageAccounts/fileServices/shares@2024-01-01' = {
  parent: fileService
  name: shareName
  properties: {
    shareQuota: 1
  }
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' existing = {
  name: containerAppsEnvironmentName
}

resource environmentStorage 'Microsoft.App/managedEnvironments/storages@2025-01-01' = {
  parent: containerAppsEnvironment
  name: environmentStorageName
  properties: {
    azureFile: {
      accountName: storageAccount.name
      accountKey: storageAccount.listKeys().keys[0].value
      shareName: share.name
      accessMode: 'ReadWrite'
    }
  }
}

output environmentStorageName string = environmentStorage.name
output storageAccountName string = storageAccount.name
