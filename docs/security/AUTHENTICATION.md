# Authentication and Authorization Model

This document describes the identity and role model implemented in
`backend/app/core/auth.py`. For the full inventory of which routes require
which role, see `docs/security/AUTHORIZATION_MATRIX.md` (maintained
separately, alongside `auth.py` itself) — this document covers the trust
model and role semantics, not the per-route enumeration.

## Trust model: Azure Container Apps Easy Auth headers

`backend/app/core/auth.py`'s `resolve_principal` derives the caller's
identity from the `X-MS-CLIENT-PRINCIPAL-ID` (and, for future claim use,
`X-MS-CLIENT-PRINCIPAL`) HTTP headers. **These headers are trusted
unconditionally by the backend** — there is no signature verification of
the header contents inside the FastAPI application itself.

This is safe **only because, and only when**, the following deployment
assumption holds:

> The backend container is never independently, publicly reachable. It is
> reachable exclusively through the frontend nginx sidecar inside the same
> Container App (see `frontend/nginx.conf.template`, `frontend/Dockerfile`),
> and, above that, through Azure Container Apps ingress with Easy Auth
> (Entra ID authentication) enabled. Azure Container Apps' built-in
> authentication middleware is what actually authenticates the caller and
> sets these `X-MS-CLIENT-PRINCIPAL*` headers on the request before it ever
> reaches nginx or the FastAPI app — it strips/overwrites any such header an
> external caller tries to forge.

If this assumption is ever broken — for example, by exposing the backend
container's port directly on a public ingress rule, or by disabling Easy
Auth on the Container App — the header-based trust model becomes forgeable
by any external caller. `docs/deployment/AZURE_ARCHITECTURE.md` documents
the network topology this relies on; any change to that topology must
re-examine this assumption explicitly, not incidentally.

## Roles

`Role` in `backend/app/core/auth.py` is an ordered `IntEnum`
(`VIEWER < ANALYST < ADMIN`); `require_role(minimum)` denies (403) any
caller whose role is below `minimum`.

| Role | How it is granted |
|---|---|
| `VIEWER` | Default for anonymous (unauthenticated) requests, when `ALLOW_ANONYMOUS_VIEWER=true` (the default). No principal header required. |
| `ANALYST` | Any request carrying a valid `X-MS-CLIENT-PRINCIPAL-ID` header — i.e. any authenticated Entra principal, with no further allow-listing. |
| `ADMIN` | An authenticated principal whose `X-MS-CLIENT-PRINCIPAL-ID` value appears in the `ADMIN_PRINCIPAL_IDS` configuration list (`backend/app/core/config.py`). |

If `ALLOW_ANONYMOUS_VIEWER=false` and no principal header is present, the
request is rejected with `401 Unauthorized` rather than being treated as
`VIEWER`.

## Development bypass: `AUTH_DEV_BYPASS_ROLE`

For local development, `AUTH_DEV_BYPASS_ROLE` (one of `VIEWER`, `ANALYST`,
`ADMIN`) makes every request resolve to that role unconditionally, without
needing Easy Auth headers at all — see `resolve_principal`'s first branch.
This is strictly a development convenience.

It is hard-blocked in production by two independent checks so a
misconfiguration cannot silently ship:

1. A pydantic validator on `Settings` in `backend/app/core/config.py`
   (`model_post_init`) raises at settings-construction time if
   `environment == "production"` and `auth_dev_bypass_role` is set.
2. `backend/app/main.py`'s `ensure_production_auth_safe`, called during
   application startup (`lifespan`), performs the same check again and
   raises a `ConfigurationError` that prevents the app from starting.

Both checks exist so the failure mode is "the application refuses to start"
rather than "the bypass silently activates in production."
