# Deterministic Attack-Path Engine

`app/services/attack_graph_service.py` computes ranked, explainable
attack paths over the existing synthetic Digital Twin topology. It is
not a second graph model: every path is enumerated over the exact same
`topology_service.nodes()` / `topology_service.edges()` data every other
Digital Twin feature already renders, and every observed/inferred/
predicted claim is resolved via the exact same sequence-bounded evidence
computation (`topology_path_service.run_state`) the existing Digital
Twin path/observed-state views already use. There is no random or
LLM-generated intelligence anywhere in this module — every field on
every returned `AttackPath` is a deterministic function of graph data
and/or persisted evidence that existed before the request was made.

## The four path types

`AttackPathType` (`app/schemas/attack_graph.py`) is a closed, explicit
vocabulary. These are never conflated with one another:

| Type | Edge set | Requires a run? | Meaning |
|---|---|---|---|
| `potential` | All `permitted` static edges | No | "Could this happen, given the declared architecture, regardless of whether it ever has?" |
| `observed` | Only edges telemetry has actually exercised (`run_state().observed_edge_ids`) through the given sequence | Yes | "Has this actually happened, according to real generated telemetry, as of this point in the run?" |
| `inferred` | Observed edges, extended exactly one hop via the static graph from assets already flagged anomalous-observed | Yes | "Given what's actually anomalous so far, what's the next static-graph-permitted step an attacker could plausibly take?" — one hop only, never chained further |
| `predicted` | Observed edges plus the existing prediction pipeline's `predicted_edge_ids` | Yes | "What does the existing, already-approved next-stage prediction model say comes next?" — this module never predicts anything itself, it only borrows `prediction_service`'s output |

## Relationship semantics (`_attack_semantics`)

The existing topology has no first-class Identity/Role/Credential graph
model, and adding one was judged too large and too risky a change for
this phase (see ADR-004). Instead, `_attack_semantics()` derives a
short, deterministic relationship label — `uses_identity`,
`can_administer`, `writes_to`, `reads_from`, `routes_to`,
`network_reachable`, `deployed_on`, `reports_to`, `manages_backup_of` —
purely from each edge's existing `destination.asset_type` and
`edge.protocol_label` / `edge.trust_level` fields. `can_administer` in
particular is only assigned when `edge.trust_level == "elevated"`,
which is also what `_is_privileged()` uses to flag a step as a
privilege-escalation hop. Nothing here invents new topology data; it
only labels relationships that already exist.

## Path enumeration (`_enumerate_paths`)

Breadth-first over path *prefixes* (not over nodes), so shorter paths
are always discovered before longer ones and the search terminates in
`O(nodes + edges)` regardless of cycles in the underlying graph — a
node already on the current path is never re-added, so every returned
path is simple (no repeated node) by construction. Bounded by
`max_depth` (1-10, default 6) and enumerates `max_paths * 3` candidates
before scoring, so the final ranking has more than the minimum to choose
from. When no explicit `target_asset_id` is given, only nodes with
`criticality in {high, critical}` or `sensitivity in {restricted,
highly_restricted}` are accepted as path endpoints — undirected
"go everywhere" enumeration would not be a meaningful attack path.

## Attack Path Priority Score

`_score()` computes `AttackPathScore.total`, a 0-100 value, as the sum
of five independently-reported contributions, floor-clamped to 0 and
ceiling-clamped to 100:

| Contribution | Formula | Rationale |
|---|---|---|
| Exposure | `25.0` if the path's source is in `edge_zone` or is an `external_client`, else `0.0` | An internet-reachable starting point is inherently higher-priority than one that already requires prior access |
| Privilege | `min(20.0, 10.0 * count(edges with trust_level == "elevated"))` | Each elevated-trust hop the path crosses raises the priority, capped at 2 such hops |
| Critical target | `min(30.0, CRITICALITY_WEIGHT[target.criticality] + SENSITIVITY_BONUS.get(target.sensitivity, 0))` where `CRITICALITY_WEIGHT = {low:0, medium:10, high:20, critical:30}` and `SENSITIVITY_BONUS = {highly_restricted:10, restricted:5}` | What's actually at the end of the path matters most |
| Boundary crossing | `min(20.0, 5.0 * count(adjacent hops whose source/destination zones differ))`, computed via `itertools.pairwise` over the path's zone sequence | Crossing a trust boundary (e.g. `edge_zone` → `workload_zone`) is itself a meaningful escalation signal |
| Evidence | `predicted` paths always score `5.0` here (the evidence is one level removed — a prediction, not direct observation); every other type scores `min(30.0, 10.0 * count(path nodes that are also flagged evidence assets))` | A path corroborated by real anomalous-observed assets is more actionable than a purely theoretical one |
| Length penalty | `max(0, hop_count - 3) * 3.0`, subtracted | All else equal, a shorter path to the same target is a more urgent finding |

Every one of these numbers is returned on `AttackPath.score` alongside
the total, so a reviewer can verify the total by hand from the reported
components — nothing is hidden inside an opaque single number.

## Determinism and ranking

Candidates are sorted by `(-score.total, hop_count, path_id)` — a pure
function of already-computed values, so two calls with identical inputs
always return identical output in identical order. `path_id` is
constructed from the ordered asset id chain plus the path type
(`"a-b-c:potential"`), so it is stable and human-readable, not a random
UUID.

## API

`GET /api/v1/attack-graph/paths` (see `app/api/routes/attack_graph.py`)
takes `source_asset_id` (required), `path_type` (default `potential`),
optional `target_asset_id`, `simulation_run_id`, `model_id`,
`through_sequence_number`, `max_depth` (1-10, default 6), `max_paths`
(1-10, default 5). Returns `AttackPathAnalysisResult`. Unknown assets
raise `ATTACK_GRAPH_ASSET_NOT_FOUND` (404); requesting a non-`potential`
path type without a `simulation_run_id` raises `ATTACK_GRAPH_RUN_REQUIRED`
(422).

## Events

The top-ranked path from each analysis (when any candidate is found)
publishes `attack.path.discovered` (`AttackPathDiscoveredPayload`) —
see `docs/architecture/EVENT_MODEL.md`.
