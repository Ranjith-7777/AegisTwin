// AegisArena — Azure Database for PostgreSQL Flexible Server (Burstable, dev-sized).
//
// NETWORK TRADEOFF (documented deliberately): Container Apps Consumption
// workload profile does not support VNet integration / private endpoints in
// the same low-cost, low-complexity way a dedicated/premium workload profile
// would. The pragmatic choice for this student-project scope is:
//   - Public network access on the Postgres server, restricted only by the
//     standard "Allow public access from any Azure service within Azure to
//     this server" firewall rule (0.0.0.0-0.0.0.0) — this does NOT open the
//     server to the whole internet, only to Azure's own service backbone.
//   - `require_secure_transport = ON` so every connection is forced over TLS
//     regardless of network path.
// A private-endpoint / VNet-integrated design would cost more (VNet, NAT/
// private DNS zone, a workload-profile Container Apps environment) and adds
// complexity disproportionate to this project's scope. Flagged as a Phase 7+
// hardening opportunity if the project ever needs it.

@description('Azure region for the server.')
param location string

@description('Base name for the server. A short deterministic suffix (uniqueString of the resource group id) is appended because Postgres Flexible Server names are globally-unique DNS names, without breaking idempotent re-deployment.')
param serverBaseName string = 'psql-aegisarena-dev'

@description('Administrator login name.')
param administratorLogin string = 'aegisadmin'

@secure()
@description('Administrator password. No default — must be supplied at deploy time and never committed to the repo.')
param administratorLoginPassword string

@description('Name of the application database created on this server.')
param databaseName string = 'aegisarena'

@description('Name of the Key Vault to write the resulting database-url secret into.')
param keyVaultName string

var serverName = '${serverBaseName}${take(uniqueString(resourceGroup().id), 4)}'

// SKU note: Standard_B1ms is the smallest practical Burstable tier for
// Microsoft.DBforPostgreSQL/flexibleServers, explicitly approved by the PM
// for this dev environment. (Verified against Azure's current PostgreSQL
// Flexible Server SKU list at authoring time; re-confirm with
// `az postgres flexible-server list-skus --location <region>` before first
// deploy in case regional availability has changed.)
resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: serverName
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword
    storage: {
      storageSizeGB: 32
    }
    highAvailability: {
      mode: 'Disabled'
    }
    // No read replica, no HA — matches PM scope exactly.
  }
}

resource appDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgresServer
  name: databaseName
}

// Standard "Allow public access from any Azure service within Azure to this
// server" rule — see network tradeoff note above.
resource allowAzureServicesFirewallRule 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: postgresServer
  name: 'AllowAllAzureServicesAndResourcesWithinAzureIps'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// TLS is already enforced by default on Flexible Server, but this makes the
// requirement explicit and future-proof against a default changing upstream.
resource requireSecureTransport 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2024-08-01' = {
  parent: postgresServer
  name: 'require_secure_transport'
  properties: {
    value: 'ON'
    source: 'user-override'
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2024-11-01' existing = {
  name: keyVaultName
}

// The connection string is built entirely from the @secure() password
// parameter and written straight into Key Vault — it is never emitted as a
// plain output, logged, or persisted anywhere else by this template.
resource databaseUrlSecret 'Microsoft.KeyVault/vaults/secrets@2024-11-01' = {
  parent: keyVault
  name: 'database-url'
  properties: {
    value: 'postgresql+psycopg://${administratorLogin}:${administratorLoginPassword}@${postgresServer.properties.fullyQualifiedDomainName}:5432/${databaseName}?sslmode=require'
  }
}

output postgresServerName string = postgresServer.name
output postgresServerFqdn string = postgresServer.properties.fullyQualifiedDomainName
