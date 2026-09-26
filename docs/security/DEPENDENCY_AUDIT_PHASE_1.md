# Frontend Dependency Security Audit — Phase 1

Date: 2026-09-13

## Summary

Phase 0 reported 11 `npm audit` findings (4 moderate, 7 high) in `frontend/`.
All 11 were transitive (development or transitive-production) dependencies,
none required a breaking/major upgrade, and all were resolved by
`npm audit fix` (no `--force`). Post-fix: **0 vulnerabilities**.

## Findings (pre-fix state)

| Package | Severity | Direct? | Vulnerable range | Fixed version | Breaking? |
|---|---|---|---|---|---|
| brace-expansion | high | no (transitive, 2 copies) | `<=1.1.17 \|\| 4.0.0-5.0.8` | 1.1.18 / 5.0.9 | No (patch) |
| browserslist | high | no (transitive) | `<=4.28.6` | 4.28.9 | No (patch) |
| fast-uri | high | no (transitive, via ajv) | `3.0.0-3.1.5` | 3.1.7 | No (patch) |
| js-yaml | high | no (transitive) | `4.0.0-4.3.1` | 4.3.2 | No (patch) |
| nanoid | high | no (transitive, via postcss chain) | `<3.3.18` | 3.3.19 | No (patch) |
| react-router | high | no (transitive, react-router-dom's dependency) | `7.12.0-7.18.1` | 7.18.3 | No (patch) |
| react-router-dom | high | **yes** (`^7.9.0` in package.json) | `7.12.0-pre.0-7.18.1` | 7.18.3 | No (patch — via react-router fix) |
| @vitest/mocker | moderate | no (transitive, vitest's dependency) | `2.1.0-4.1.10` | 4.1.11 | No (patch) |
| baseline-browser-mapping | moderate | no (transitive) | `>=2.0.0 <2.11.0` | 2.11.23 | No (patch) |
| postcss | moderate | no (transitive, via tailwindcss chain) | `<=8.5.22` | 8.5.28 | No (patch) |
| vitest | moderate | **yes** (`^4.0.4` in package.json) | `2.1.0-beta.1-4.1.10` | 4.1.11 | No (patch — via @vitest/mocker fix) |

### Relevance to this application

- `react-router-dom`/`react-router` (CWE-352, CSRF bypass in RSC/server-action mode): this app is a pure client-side SPA served static assets (see `frontend/Dockerfile`, `vite.config.ts`) and does not use React Router's server/RSC action mode — the vulnerable code path is not exercised, but the fix was free (patch bump) so it was applied anyway.
- `vitest`/`@vitest/mocker` (path traversal in mock redirect): dev-only test tooling, never shipped to production; still fixed since it was free.
- `browserslist`/`baseline-browser-mapping`/`postcss`/`nanoid`/`js-yaml`/`fast-uri`/`brace-expansion`: all are build-time/dev-time transitive tooling (Tailwind/PostCSS/ESLint/Vite toolchain), not runtime application code; none are reachable from user input in the shipped app.

## Fix applied

```
npm audit fix
```

(no `--force`; `npm audit fix --dry-run --json` was inspected first — all 23 resulting package changes were patch or minor version bumps, none flagged `isSemVerMajor`). Followed by `npm ci` to ensure `node_modules` fully matched the updated `package-lock.json`.

## Post-fix verification (all green)

| Command | Result |
|---|---|
| `npm audit` | 0 vulnerabilities |
| `npm run lint` | PASS |
| `npm run typecheck` | PASS |
| `npm run format:check` | PASS |
| `npm run test:run` | PASS (43/43 tests) |
| `npm run build` | PASS |

## Deferred for later (none in this case)

No vulnerability in this audit required a major/breaking upgrade. If a future audit surfaces one requiring a major version bump (e.g. a React Router v8 migration), it should be evaluated and scheduled as its own change, not folded into a routine dependency-audit pass — document it here rather than forcing the upgrade.
