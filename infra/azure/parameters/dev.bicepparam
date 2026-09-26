using '../main.bicep'

// Non-secret parameters for the dev environment. Safe to commit.
param location = 'centralindia'
param resourceGroupName = 'rg-aegisarena-dev'

// Placeholder only — the deploying CI workflow MUST override this with the
// immutable git-sha tag of the images it just pushed. Never deploy with
// "latest" outside of local, throwaway iteration.
param imageTag = 'latest'

param minReplicas = 0
param maxReplicas = 1

param postgresAdministratorLogin = 'aegisadmin'

// SECURITY: the admin password is never written to this file (or any file
// committed to git). It is read from the PGADMIN_PASSWORD environment
// variable at deploy time, which the CI workflow populates from a GitHub
// Actions secret (or an operator sets locally before a manual deploy, e.g.
// generated once with `openssl rand -base64 32` and stored directly into
// Key Vault / a secret manager — never typed into a param file).
param postgresAdministratorPassword = readEnvironmentVariable('PGADMIN_PASSWORD')
