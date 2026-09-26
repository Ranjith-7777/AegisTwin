# Deployment Requirements

Use `backend/.env.production.example` and `frontend/.env.production.example` as explicit templates. Keep `SIMULATION_ONLY=true` and `DEBUG=false`. Configure exact HTTPS CORS origins, API and WebSocket public URLs, database location, and a writable model-artifact directory.

Run `alembic upgrade head` before starting the API. `/api/health` remains a lightweight connectivity probe; `/api/status` and `/api/system/status` describe simulation state. Serve the frontend as static files and route API/WebSocket traffic to the backend.

SQLite deployments should use one application worker. The artifact cache and WebSocket connection manager are process-local. Multi-worker or horizontally scaled operation requires architecture beyond this prototype. Do not add credentials to `VITE_*` variables because they are embedded in public bundles.
