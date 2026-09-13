# Estimated Synthetic Blast-Radius

`app/services/blast_radius_service.py` estimates what else in the
synthetic estate would be affected if a given set of assets were
compromised. It is explicitly an *estimate over the synthetic graph*,
computed once per request from real topology data — never a production
blast-radius claim, and never based on random or fabricated data.

## Why the traversal always uses the full static graph

Unlike the Attack Graph engine's `observed`/`inferred`/`predicted` path
types, blast-radius estimation always traverses the full set of
`permitted` static edges, regardless of whether a `simulation_run_id`
is supplied. This is a deliberate, conservative choice: blast radius
answers "what *could* be reached from here, worst case", not "what
*has* been reached so far" — the latter question is already answered by
the Attack Graph engine's `observed` path type. When a `run_id` is
given, `topology_path_service.run_state(...)` is still called, but only
to confirm the requested compromised assets are consistent with what
has actually been observed in that run; it never narrows or changes the
traversal itself.

## Algorithm

1. **Forward reachability** (`_forward_reachable`): breadth-first from
   every compromised asset, only over `edge.permitted` edges, bounded by
   `max_depth` (1-10, default 6). Cycle-safe by construction (a node is
   enqueued at most once via a `visited` set), so termination is
   guaranteed in `O(nodes + edges)` regardless of cycles.
2. **Dependents**: assets with a permitted edge *into* the
   compromised-or-reachable set that are not themselves in it — i.e.
   things that call or depend on what's compromised/reachable and would
   be operationally impacted even though they are not themselves
   attacker-reachable (e.g. a load balancer that routes to a compromised
   pod is a dependent, not something the attacker can pivot into).
3. **Critical assets at risk**: the subset of
   compromised ∪ reachable ∪ dependents with `criticality in {high,
   critical}`.
4. **Trust zones reached**: the distinct `zone` values across every
   asset in that same union.

## Estimated Synthetic Blast-Radius Score

`BlastRadiusScore.total`, a 0-100 value, clamped at 100:

| Contribution | Formula |
|---|---|
| Reachable | `len(reachable) * 2.0` |
| Critical asset | `critical_count * 10.0` |
| Sensitive asset | `sensitive_count * 5.0` (assets with `sensitivity in {restricted, highly_restricted}`) |
| Zone crossing | `len(trust_zones_reached) * 5.0` |

Each contribution is reported independently on `BlastRadiusResult.score`
alongside the total.

## API

`POST /api/v1/blast-radius` (see `app/api/routes/blast_radius.py`) takes
a `BlastRadiusQuery` body: `compromised_asset_ids` (1-10 items,
required), optional `simulation_run_id`, `through_sequence_number`,
`max_depth` (1-10, default 6). Returns `BlastRadiusResult`. An unknown
asset id raises `BLAST_RADIUS_ASSET_NOT_FOUND` (404).

## Events

Every estimate publishes `blast_radius.assessed`
(`BlastRadiusAssessedPayload`) — see `docs/architecture/EVENT_MODEL.md`.
