# Phase 6A: Interactive Synthetic Infrastructure Digital Twin

Phase 6A turns the repository-defined infrastructure inventory into a versioned, inspectable graph. It does not scan, discover, contact, or control any real infrastructure.

```text
Synthetic Infrastructure Inventory
          ↓
Versioned Topology Service
          ↓
Deterministic Directed Graph
          ↓
Topology and Path APIs
          ↓
React Flow Digital Twin
          ↓
Asset and Path Inspection
```

## Source of truth

`backend/app/services/infrastructure_service.py` remains the asset source of truth. The topology adapter enriches its eight assets with display types, sensitivity, descriptions, and stable zones: user, identity, application, data, and operations. The documentation-only synthetic egress sink is added only for the staged demonstration context.

No network addresses are returned by topology APIs. All nodes, edges, snapshots, run states, and paths carry `synthetic: true`.

## Relationships

Directed edges distinguish `expected_relationship`, `conditionally_allowed_relationship`, and `simulation_only_external_relationship`. Protocol values are display labels for the synthetic architecture, not connection instructions. Existing inventory relationships are preserved while the primary application flow is explicit: endpoints → authentication and portal services → application server → database and backup services. Monitoring relationships remain separate.

The topology version is `aegistwin-synthetic-topology-v1`. Node positions are a fixed zone-based frontend map and never randomly rearrange.

## Path semantics

- **Expected:** shortest path in the versioned synthetic architecture.
- **Observed:** only telemetry source/destination pairs at or before the requested sequence.
- **Correlated:** only event pairs referenced by persisted incident evidence for the requested run and model.
- **Predicted:** hypothetical pair derived from the latest eligible persisted asset hypothesis.

Observed and correlated paths cannot consume future events. Predicted results always state: “Hypothetical path derived from synthetic ranked predictions.” Run/model state is reloaded and sequence-dependent state is cleared when the selection changes.

The service uses a bounded deterministic breadth-first traversal. Graph logic remains outside API routes. NetworkX was not introduced because the graph is small and the existing stack already contains a causal breadth-first implementation pattern.

## REST contracts

- `GET /api/v1/topology`
- `GET /api/v1/topology/nodes`
- `GET /api/v1/topology/nodes/{asset_id}`
- `GET /api/v1/topology/edges`
- `GET /api/v1/topology/nodes/{asset_id}/neighbours`
- `GET /api/v1/topology/paths`
- `GET /api/v1/topology/runs/{run_id}/state`

Path queries accept source, destination, path type, optional run/model scope, through-sequence limit, and maximum paths. Missing assets and unreachable paths use structured application errors.

## Frontend architecture and accessibility

`useTopology` owns topology loading, selection, run state, errors, and path results. Runtime parsers reject malformed nodes, edges, snapshots, states, and paths. React Flow provides zoom, pan, fit view, controls, a minimap, and keyboard-focusable asset nodes. Labels, border styles, badges, and textual summaries supplement colour. Mobile uses a reduced node footprint and scroll-safe fixed canvas.

The full Digital Twin page includes asset/relationship inspection, zone and path legends, visibility layers, run/model/sequence controls, and path inspection. Overview reuses the same graph in compact mode.

## Current limitations

The graph is intentionally small and static. Phase 6A does not animate sequence changes, infer compromise, report health or availability, execute response actions, or introduce agents, LLMs, RAG, live topology discovery, or external connectivity. Sequence-driven animation belongs to Phase 6B.
