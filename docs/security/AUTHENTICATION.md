# Authentication and Authorization Model

This document describes the identity and role model implemented in
`backend/app/core/auth.py`. For the full inventory of which routes require
which role, see `docs/security/AUTHORIZATION_MATRIX.md` (maintained
separately, alongside `auth.py` itself) — this document covers the trust
model and role semantics, not the per-route enumeration.

## Trust model: `TRUST_EASYAUTH_HEADERS` gates Easy Auth headers, defaulting to false

`backend/app/core/auth.py`'s `resolve_principal` can derive the caller's
identity from the `X-MS-CLIENT-PRINCIPAL-ID` (and, for future claim use,
`X-MS-CLIENT-PRINCIPAL`) HTTP headers — but **only when
`Settings.trust_easyauth_headers` is explicitly `True`**
(`TRUST_EASYAUTH_HEADERS` env var). This defaults to `False` everywhere,
including production, and is a completely separate switch from
`ENVIRONMENT=production`.

This exists because the Bicep in this phase (`infra/azure/main.bicep`)
provisions the Container App **without** configuring Azure Container Apps
Easy Auth — the actual Microsoft Entra application registration is a manual
step performed during hosting (see "Manual hosting sequence" below), after
the Container App already exists. Between the Container App being created
and an operator manually finishing that Easy Auth setup, there is a window
where the backend would otherwise be reachable without any real
authentication proxy in front of it. Trusting `X-MS-CLIENT-PRINCIPAL*`
headers unconditionally during that window would let any caller who can
reach the backend forge those headers directly and grant themselves
ANALYST or ADMIN. `TRUST_EASYAUTH_HEADERS=false` closes that window: the
headers are ignored outright, so the caller falls through to, at most,
anonymous VIEWER (or `401` if `ALLOW_ANONYMOUS_VIEWER=false`) — see
`backend/tests/test_authorization.py`'s
`test_production_default_trust_false_spoofed_header_stays_viewer` and
`test_trust_false_and_anonymous_disabled_ignores_header_and_401s` for the
exact proof.

**`TRUST_EASYAUTH_HEADERS=true` is safe only once, and only after**, the
following deployment assumption is actually true — not assumed, verified:

> The backend container is never independently, publicly reachable. It is
> reachable exclusively through the frontend nginx sidecar inside the same
> Container App (see `frontend/nginx.conf.template`, `frontend/Dockerfile`),
> and, above that, through Azure Container Apps ingress with Easy Auth
> (Entra ID authentication) genuinely configured and enabled. Azure
> Container Apps' built-in authentication middleware is what actually
> authenticates the caller and sets these `X-MS-CLIENT-PRINCIPAL*` headers
> on the request before it ever reaches nginx or the FastAPI app — it
> strips/overwrites any such header an external caller tries to forge.

**Manual hosting sequence** (see `docs/deployment/AZURE_DEPLOYMENT.md` for
the full ordered command sequence, including bootstrap):

1. Deploy the Container App (with `TRUST_EASYAUTH_HEADERS` left at its
   default `false` — Bicep never sets it to `true`).
2. Create/configure the Microsoft Entra application registration and enable
   Container Apps Easy Auth on the running Container App, keeping
   unauthenticated access allowed (so public VIEWER behavior still works).
3. Verify authentication actually works end-to-end — e.g. hit
   `/.auth/login/aad`, confirm a real sign-in flow, and confirm the
   `X-MS-CLIENT-PRINCIPAL*` headers the backend receives are genuinely
   Easy-Auth-issued (not forgeable by a direct caller).
4. **Only then** set `TRUST_EASYAUTH_HEADERS=true` on the Container App and
   redeploy/update the revision.
5. Re-test VIEWER (anonymous), ANALYST (authenticated), and ADMIN
   (configured principal ID) behavior against the live deployment.

If this assumption is ever broken later — for example, by exposing the
backend container's port directly on a public ingress rule, or by disabling
Easy Auth on the Container App after having set `TRUST_EASYAUTH_HEADERS=true`
— the header-based trust model becomes forgeable again. Setting
`TRUST_EASYAUTH_HEADERS` back to `false` immediately restores the safe
fallback (anonymous VIEWER / 401) without any code change.
`docs/deployment/AZURE_ARCHITECTURE.md` documents the network topology this
relies on; any change to that topology must re-examine this assumption
explicitly, not incidentally.

## Roles

`Role` in `backend/app/core/auth.py` is an ordered `IntEnum`
(`VIEWER < ANALYST < ADMIN`); `require_role(minimum)` denies (403) any
caller whose role is below `minimum`.

| Role | How it is granted |
|---|---|
| `VIEWER` | Default for anonymous (unauthenticated) requests, when `ALLOW_ANONYMOUS_VIEWER=true` (the default). No principal header required, regardless of `TRUST_EASYAUTH_HEADERS`. |
| `ANALYST` | **Only when `TRUST_EASYAUTH_HEADERS=true`**: any request carrying a valid `X-MS-CLIENT-PRINCIPAL-ID` header — i.e. any authenticated Entra principal, with no further allow-listing. When `TRUST_EASYAUTH_HEADERS=false` (the default), this header is ignored and cannot grant ANALYST. |
| `ADMIN` | **Only when `TRUST_EASYAUTH_HEADERS=true`**: an authenticated principal whose `X-MS-CLIENT-PRINCIPAL-ID` value appears in the `ADMIN_PRINCIPAL_IDS` configuration list (`backend/app/core/config.py`). Also ignored entirely when `TRUST_EASYAUTH_HEADERS=false`. |

If `ALLOW_ANONYMOUS_VIEWER=false` and no principal header resolves to a role
(either because none was sent, or because `TRUST_EASYAUTH_HEADERS=false`
caused it to be ignored), the request is rejected with `401 Unauthorized`
rather than being treated as `VIEWER`.

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
