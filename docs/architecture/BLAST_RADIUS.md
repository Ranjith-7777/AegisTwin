# Estimated Synthetic Blast-Radius

`app/services/blast_radius_service.py` estimates what else in the
synthetic estate would be affected if a given set of assets were
compromised. It is explicitly an *estimate over the synthetic graph*,
computed once per request from real topology data — never a production
blast-radius claim, and never based on random or fabricated data.

## Run/sequence semantics: two explicit modes (`BlastRadiusResult.mode`)

The traversal always uses the full set of `permitted` static edges
regardless of mode — that part is unchanged and deliberate: blast radius
answers "what *could* be reached from here, worst case", not "what
*has* been reached so far" (the latter question is already answered by
the Attack Graph engine's `observed` path type). What changed is what
"compromised" is allowed to mean:

* **`hypothetical`** — no `simulation_run_id` supplied. A static
  what-if: any asset may be named as compromised, with no claim that it
  has actually happened. This is the original, unconditional behavior.
* **`evidence_bound`** — a `simulation_run_id` is supplied. Every id in
  `compromised_asset_ids` is checked against
  `topology_path_service.run_state(...)`'s `observed_asset_ids ∪
  anomalous_observed_asset_ids` computed through `through_sequence`
  (never a later sequence — this is the same sequence-bounding
  guarantee `topology_path_service.run_state` already enforces
  everywhere else it's used). An asset not supported by evidence at
  that point in the run raises `BLAST_RADIUS_EVIDENCE_REQUIRED` (422)
  rather than being silently accepted or silently downgraded to
  hypothetical — chosen over the "mark hypothetical" alternative
  because a caller who explicitly supplied a `run_id` has asked for an
  evidence-bound answer, and a silent mode switch would let a caller
  believe they got one when they didn't. `through_sequence_number` on
  the response is the *resolved* sequence limit (never the raw,
  possibly-`None` input), so it's always inspectable.

The traversal itself never narrows based on evidence — it always uses
the full permitted static graph. Evidence only bounds the *starting
set*, never the graph the search is run over.

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
asset id raises `BLAST_RADIUS_ASSET_NOT_FOUND` (404); an asset
unsupported by evidence at the given sequence (evidence-bound mode
only) raises `BLAST_RADIUS_EVIDENCE_REQUIRED` (422).

## Events

Every estimate publishes `blast_radius.assessed`
(`BlastRadiusAssessedPayload`) — see `docs/architecture/EVENT_MODEL.md`.
