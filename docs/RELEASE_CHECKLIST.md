# Release Checklist

- [ ] `SETUP_AEGISTWIN_DEMO.bat` completes on the judge laptop
- [ ] Production one-click startup reaches backend and frontend readiness
- [ ] Status, stop, reset, offline audit, and packaged smoke workflows pass

- [ ] Simulation-only startup enforcement remains active
- [ ] Backend Ruff, mypy, pytest, and clean migration pass
- [ ] Frontend Prettier, ESLint, TypeScript, Vitest, and build pass
- [ ] Playwright primary and focused E2E workflows pass on a fresh database
- [ ] Audit integrity and rollback assertions pass
- [ ] Benchmark JSON, CSV, and Markdown regenerate successfully
- [ ] Base topology immutability assertion passes
- [ ] Browser console contains no errors
- [ ] No databases, artifacts, secrets, or local absolute paths are tracked
- [ ] README and demo instructions match current behavior
- [ ] No deployment, commit, or push occurs automatically
