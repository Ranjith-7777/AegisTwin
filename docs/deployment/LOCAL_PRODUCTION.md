# Running a Production-like Stack Locally

`docker-compose.prod.yml` at the repository root builds and runs the
production Dockerfiles (`backend/Dockerfile`, `frontend/Dockerfile`) locally,
so the production container images and nginx reverse-proxy configuration can
be exercised without deploying to Azure. See that file at the repository
root for the exact service definitions, ports, and environment variables it
sets — it is authored and maintained alongside the Dockerfile changes in
this same phase, so refer to it directly rather than a description here
going stale.

## General usage

```bash
docker compose -f docker-compose.prod.yml up --build
```

Bring the stack down (and remove volumes, if you want a clean database)
with:

```bash
docker compose -f docker-compose.prod.yml down -v
```

## Why this matters

The production images run a single uvicorn worker and serve the frontend as
static files through nginx, proxying `/api` and `/ws` to the backend — this
differs meaningfully from the `npm run dev` / `uvicorn --reload` local
development loop. Running `docker-compose.prod.yml` locally is the fastest
way to catch issues that only show up in the production container shape
(e.g. nginx proxy rules, environment variable wiring, `alembic upgrade head`
running correctly on container start) before pushing an image to Azure.

See also `docs/DEPLOYMENT_REQUIREMENTS.md` for the underlying environment
variable and single-worker constraints that both `docker-compose.prod.yml`
and the Azure deployment share.
