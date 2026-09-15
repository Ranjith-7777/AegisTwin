# Production Hardening Summary

This document summarizes the hardening measures active when
`ENVIRONMENT=production`. It is a summary/index — see the referenced source
files for the authoritative behavior.

## API documentation disabled

`backend/app/main.py`'s `create_app` computes
`docs_enabled = active_settings.docs_enabled and active_settings.environment != "production"`
and passes `docs_url`/`redoc_url`/`openapi_url` as `None` when
`docs_enabled` is false. In production this means `/docs`, `/redoc`, and
`/openapi.json` are all disabled regardless of the `DOCS_ENABLED` setting —
production always wins.

## Security headers

- **Backend**: `SecurityHeadersMiddleware` in `backend/app/core/middleware.py`
  sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin`, a restrictive
  `Permissions-Policy`, and a minimal
  `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` —
  appropriate because these responses are API JSON, never rendered HTML.
- **Frontend**: the full page Content-Security-Policy (script/style/connect
  sources appropriate for the React SPA) is applied by the production nginx
  layer — see `frontend/nginx.conf` for the exact policy (authored alongside
  the Dockerfile/nginx changes in this phase; not duplicated here to avoid
  the two drifting apart).

## CORS

CORS is environment-driven via `CORS_ORIGINS`
(`backend/app/core/config.py`), and `validate_cors_origins` rejects a
wildcard (`*`) origin and any origin not using `http://`/`https://`. This
behavior predates Phase 6 and is unchanged by it — it is listed here for
completeness of the production hardening picture, not as a new control.

## Debug mode

`DEBUG` defaults to `false` (`backend/app/core/config.py`) and must be
explicitly set to enable it; nothing in the production deployment path sets
it to `true`.

## Fail-closed startup checks

Two settings are enforced as hard startup failures rather than warnings, so
a misconfiguration cannot silently run in production:

- **`SIMULATION_ONLY=false`**: `backend/app/main.py`'s
  `ensure_simulation_only`, run during the `lifespan` startup hook, raises a
  `ConfigurationError` (preventing the app from starting) if
  `SIMULATION_ONLY` is not true. AegisArena is prohibited from starting in
  any "real-world" (non-simulation) mode.
- **`AUTH_DEV_BYPASS_ROLE` set in production**: enforced twice —
  `Settings.model_post_init` (`backend/app/core/config.py`) raises at
  settings-construction time, and `ensure_production_auth_safe`
  (`backend/app/main.py`) raises again during startup. See
  `docs/security/AUTHENTICATION.md` for the full authentication trust model
  this protects.

Both fail-closed checks mean a production deployment with either
misconfiguration simply refuses to start, rather than serving traffic in an
unsafe mode.
