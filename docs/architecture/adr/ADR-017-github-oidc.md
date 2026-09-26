# ADR-017: GitHub OIDC Workload Identity Federation for Azure Deployment

## Status
Accepted.

## Context

`deploy-azure.yml` needs to authenticate to Azure to push container images
and run a Bicep deployment. The traditional approach for this — creating an
Azure AD service principal with a client secret and storing that secret as
a GitHub Actions secret — works, but a long-lived secret stored outside
Azure is a standing liability: it does not expire on its own, it can be
exfiltrated from GitHub's secret store or accidentally logged, and revoking
it after a suspected leak is a manual, easy-to-forget step. Azure AD
workload identity federation (OIDC) lets GitHub Actions authenticate using
a short-lived token issued per workflow run, verified against a trust
relationship configured on the Azure side, with no secret stored on the
GitHub side at all.

## Decision

Use **GitHub OIDC workload identity federation** for `deploy-azure.yml`'s
Azure authentication:

- The workflow declares `permissions: id-token: write` and uses
  `azure/login@v2`, supplying only `client-id`/`tenant-id`/
  `subscription-id` (non-secret identifiers, stored as GitHub repository
  **variables** — `vars.*`, not `secrets.*`).
- A federated credential is configured once, out-of-band (documented in
  `docs/deployment/AZURE_DEPLOYMENT.md`, created via
  `az identity federated-credential create`), binding the
  `id-aegisarena-github` managed identity to this specific repository and
  branch/environment subject claim.
- No `client-secret` input exists anywhere in the workflow — there is no
  fallback secret-based authentication path to accidentally fall back on.

The identity `id-aegisarena-github` used for this federation is scoped to
least privilege: `AcrPush` on the registry and **`Contributor` scoped to
the resource group** `rg-aegisarena-dev` only — not subscription-level
`Owner` or `Contributor`. Even if a workflow run were somehow compromised,
the blast radius is bounded to this one resource group and this one
registry, never the subscription as a whole. See
`docs/security/SECRETS_AND_IDENTITY.md` for the full identity/role-
assignment breakdown.

## Alternatives considered

1. **Service principal with a client secret, stored as a GitHub Actions
   secret.** Rejected: a long-lived credential stored outside Azure is a
   standing risk with no automatic expiry, and every rotation is a manual
   operational task someone has to remember to do. OIDC removes this
   category of risk entirely — there is no secret to leak because none is
   issued to GitHub in the first place.
2. **Subscription-level `Owner`/`Contributor` on the deploy identity, to
   avoid having to enumerate exact permissions.** Rejected: violates
   least-privilege for no operational benefit — this project only ever
   needs to act within one resource group and push to one registry, so
   scoping to that resource group bounds the damage of any future
   misconfiguration or compromise without costing anything in convenience.
3. **GitHub OIDC federation, RG-scoped Contributor + registry-scoped
   AcrPush (chosen).** No stored secret, and the identity's permissions
   match exactly what the deployment actually needs to do.

## Consequences

- Positive: no Azure credential exists in GitHub's secret store for this
  workflow — the only genuine secret it handles is `PGADMIN_PASSWORD`
  (Postgres admin password), which is unavoidably a real secret regardless
  of authentication method.
- Positive: the federated credential's subject claim (bound to a specific
  repo/branch/environment) means a token issued to a different repository
  or workflow cannot be exchanged for access to these Azure resources.
- Positive: RG-scoped Contributor means a compromised or buggy workflow run
  cannot affect resources outside `rg-aegisarena-dev`, or read/modify other
  subscriptions' resources.
- Negative: the one-time federated-credential setup step
  (`az identity federated-credential create`) is a manual, out-of-band
  action that Bicep intentionally does not automate (it names a specific
  GitHub repo/branch, which is an operator decision) — documented in
  `docs/deployment/AZURE_DEPLOYMENT.md` so it is not forgotten.

## Future reconsideration trigger

Revisit if this project ever needs to deploy from multiple repositories or
CI providers simultaneously, which would require either multiple federated
credentials or a broader trust policy — worth re-evaluating scope at that
point rather than widening it preemptively now.
