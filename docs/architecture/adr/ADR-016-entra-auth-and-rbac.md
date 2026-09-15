# ADR-016: Entra/Container-Apps-Header Identity With a 3-Tier RBAC Model

## Status
Accepted.

## Context

Phase 6 needs some notion of "who is calling" and "what are they allowed to
do" once the application is reachable over the public internet, rather than
only on a developer's own machine. Building and operating a custom
username/password authentication system (registration, password storage
and hashing, session/token issuance and rotation, password reset flows) is
a substantial, security-sensitive surface area that this project has no
particular need to own, given that the deployment target (Azure Container
Apps) already offers built-in authentication.

## Decision

Use **Azure Container Apps' built-in authentication ("Easy Auth") with
Entra ID** as the identity provider in front of the application, and
implement a backend-enforced, three-tier role model
(`backend/app/core/auth.py`):

- `VIEWER` — default for anonymous requests (when
  `ALLOW_ANONYMOUS_VIEWER=true`).
- `ANALYST` — granted to any authenticated Entra principal, with no further
  allow-listing required.
- `ADMIN` — granted only to principals whose ID appears in the
  `ADMIN_PRINCIPAL_IDS` configuration.

Role resolution reads the `X-MS-CLIENT-PRINCIPAL-ID` header that Container
Apps' authentication middleware sets on the request. **This relies on an
explicit trust-boundary assumption**: the backend must never be
independently, publicly reachable — it is reachable only through the
frontend nginx sidecar and, above that, through Container Apps ingress with
Easy Auth enabled, which is what actually authenticates callers and sets
(and cannot be spoofed past) that header. See
`docs/security/AUTHENTICATION.md` for the full statement of this assumption
and the deployment topology it depends on.

## Alternatives considered

1. **Custom username/password system with a local `users` table, hashed
   passwords, and issued session tokens/JWTs.** Rejected: this is a large,
   security-sensitive subsystem (password storage, rotation, reset flows,
   token revocation) to build and maintain for a student project, when the
   hosting platform already provides equivalent authentication for free.
   Every additional line of custom auth code is additional attack surface
   this project would be solely responsible for getting right.
2. **A general-purpose external IdP integration (e.g. Auth0, direct OAuth
   library integration) independent of the hosting platform.** Rejected as
   unnecessary complexity: since the deployment target is already Azure
   Container Apps, its native Easy Auth/Entra integration achieves the same
   authentication outcome with less code and fewer moving parts than
   wiring an OAuth library into the FastAPI app directly.
3. **Container Apps Easy Auth + Entra ID, with backend-enforced 3-tier RBAC
   (chosen).** Delegates authentication entirely to the platform;
   authorization (role assignment and per-route enforcement) stays in
   application code where the domain-specific `VIEWER`/`ANALYST`/`ADMIN`
   semantics belong.

## Consequences

- Positive: no password storage, hashing, or session management code exists
  in this codebase at all — that entire class of vulnerability is
  structurally absent.
- Positive: the role model is simple to reason about and audit (a total
  order on three roles, one dependency function,
  `docs/security/AUTHORIZATION_MATRIX.md` enumerating every route's
  requirement).
- Negative: the model's safety depends entirely on the network topology
  assumption holding (backend never independently exposed). This is a
  single point of failure for the entire authorization model if the
  deployment configuration ever drifts — mitigated by documenting it
  explicitly (`docs/security/AUTHENTICATION.md`) rather than leaving it
  implicit, so any future infrastructure change is forced to confront it.
- Negative: coupling the identity provider to the hosting platform (Azure
  Container Apps + Entra specifically) means moving to a different hosting
  platform would require re-implementing authentication, not just
  redeploying.

## Future reconsideration trigger

Revisit if the application is ever deployed on a platform without
equivalent built-in authentication, or if finer-grained permissions beyond
a 3-tier role model become necessary.
