# Limitations and Future Work

Honest constraints, not hidden behind polish. These are discussion points
for evaluation and viva, not defects to silently patch.

## Accepted Phase 5 research limitations

1. **Single-chokepoint Mission Health topology.** The current mission-health
   graph has a characteristic where some containment actions preserve
   security while still leaving mission connectivity degraded, because a
   single chokepoint asset's health disproportionately affects the overall
   mission-health signal. This is a property of the current synthetic
   topology, not a scoring bug — it is preserved as an accurate reflection
   of what the topology actually does, and is a legitimate discussion point
   about how mission-health graphs should be designed.
2. **Canonical seed sensitivity.** The five canonical seeds used in the
   Phase 5 evaluation matrix change generated event *content* but often do
   not change the *final scored outcome*, because the random values drawn
   from them tend to stay within the same detector-threshold regions rather
   than crossing into a different one. This means the canonical matrix
   under-samples genuine outcome variance across seeds — a real limitation
   of the current seed set's coverage, not of the scoring formulas
   themselves.

## Additional limitations (Phase 6/7)

3. **Synthetic rather than live cloud mutation.** Every Red Agent action and
   every Blue Agent execution is a synthetic mutation against an in-memory
   digital twin. Nothing in this system has ever touched a real Azure
   resource, IAM policy, firewall rule, or credential. This is a deliberate
   design boundary (see `docs/final/PROJECT_OVERVIEW.md`), not a
   limitation to be lifted — but it does mean results here characterize the
   *decision and evaluation methodology*, not real-world blast radius or
   real attacker behavior.
4. **Single process / single replica runtime-state constraint.** The
   backend holds its event bus and Digital Twin simulation state in process
   memory. This means the application can only run as exactly one process
   in exactly one Container Apps replica (`maxReplicas=1`) — running
   multiple replicas or worker processes today would create diverging,
   inconsistent copies of that state. Redesigning this to be
   horizontally-scalable would require externalizing the event bus and
   twin state (e.g. to Redis/Postgres) — explicitly out of scope for this
   project's phases, and not something to be silently "fixed" with a new
   infrastructure dependency without that redesign actually happening.
5. **Cost-conscious deployment architecture.** The Azure deployment (see
   `docs/deployment/AZURE_ARCHITECTURE.md`) intentionally uses
   Consumption-tier Container Apps, a Burstable PostgreSQL SKU with no high
   availability, and scale-to-zero steady state. This is appropriate for a
   student/research project, not for a production SLA workload — a
   production deployment of these ideas would need HA database, redundant
   replicas (which requires solving limitation 4 first), and a paid Azure
   Budget/monitoring setup.
6. **Easy Auth not yet enabled.** `TRUST_EASYAUTH_HEADERS` defaults to
   `false` and Azure Container Apps Easy Auth has not yet been configured
   (hosting itself is deferred — see `docs/deployment/AZURE_DEPLOYMENT.md`).
   Until that manual step happens, every deployed instance serves anonymous
   VIEWER access only; ANALYST/ADMIN actions require either the local dev
   bypass (never available in production) or a completed Easy Auth setup.

## Realistic future work

- Externalize event-bus/twin state (Redis or Postgres-backed) to remove the
  single-replica constraint and enable horizontal scaling under real load.
- Expand the canonical seed set (or add adaptive/stratified seed sampling)
  so evaluation runs actually sample distinct threshold regions rather than
  clustering in the same ones.
- Add a second, differently-shaped mission-health topology (avoiding the
  single-chokepoint property) as a robustness check on ARS/MCI's
  sensitivity to topology design.
- Once Easy Auth is verified working, extend the ADMIN allow-list mechanism
  to a real Entra group claim instead of a static ID list, if the project
  grows beyond a handful of named administrators.
- If ever deployed for a real production SLA (out of scope for this
  project as submitted), move PostgreSQL to a HA SKU and increase
  `maxReplicas` only after the state-externalization work above is done.
