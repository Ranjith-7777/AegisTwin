# ADR-004: Attack Graph as an Additive Layer Over the Existing Topology

## Status
Accepted — Phase 3.

## Context

Phase 3 required a deterministic, fully explainable Attack Graph engine
distinguishing trust boundaries and identity/privilege relationships,
with every claimed path traceable to real graph data and real evidence
— explicitly no fake or random intelligence. The existing synthetic
topology (`topology_service.NODE_DETAILS` / `EDGE_DEFINITIONS`) already
carries `zone` (trust boundary), `criticality`, `sensitivity`, and
`trust_level` per node/edge, but has no first-class Identity, Role, or
Credential graph model — `iam-service-01`, `auth-pod-01`, and
`admin-service-01` exist only as ordinary infrastructure nodes with no
semantic distinction from, say, `cloud-database-01`.

## Decision

Represent identity/privilege semantics **additively**, without adding
new node/edge types or changing the existing 13-node/24-edge topology
data at all:

1. A new pure function, `_attack_semantics(source, destination, edge)`
   in `attack_graph_service.py`, derives a relationship label
   (`uses_identity`, `can_administer`, `writes_to`, ...) purely from
   each edge's *existing* `destination.asset_type` and
   `edge.protocol_label` / `edge.trust_level` fields.
2. Privilege escalation is flagged purely from the existing
   `edge.trust_level == "elevated"` field (`_is_privileged`).
3. Attack paths are enumerated over the existing topology graph
   unchanged; the Attack Graph engine reads `topology_service` and
   `topology_path_service`, it never writes to or extends them.

## Alternatives considered

1. **Add first-class `Identity`, `Role`, `Credential` graph node types.**
   Rejected for this phase: this would require new topology schema, new
   `NODE_DETAILS`/`EDGE_DEFINITIONS` entries, and — critically — would
   change the existing frontend's node-position layout and every
   existing topology/response/blast-radius consumer that iterates
   `topology_service.nodes()`, none of which expect identity nodes
   mixed into infrastructure nodes. This is a much larger, riskier
   change than Phase 3's actual requirement (explainable attack paths
   over what already exists), and was explicitly out of scope without
   escalation per the phase instructions ("escalate before ... replacing
   core stack pieces").
2. **A second, parallel graph model just for identity/privilege,
   correlated to the topology graph by asset id.** Rejected: this is
   exactly the "second graph model" the phase instructions explicitly
   forbade ("This module does not introduce a second graph model").
   Keeping one graph with an additive labeling function guarantees the
   Attack Graph engine can never drift out of sync with what
   `topology_service` actually returns.
3. **Infer privilege purely from node `asset_type` (e.g. "anything named
   `admin_*` is privileged").** Rejected: this would silently
   re-implement trust semantics the topology data already encodes more
   precisely via `trust_level`, risking disagreement with what
   `topology_path_service` and `response_service` already treat as
   elevated.

## Consequences

- Positive: zero risk to any existing topology/frontend/response/
  blast-radius consumer — `topology_service.NODE_DETAILS` and
  `EDGE_DEFINITIONS` are byte-for-byte unchanged by this phase.
- Positive: every attack-path step's `attack_semantics` and
  `privileged` fields are provably derived from data that already
  existed before Phase 3, satisfying "no fake intelligence" by
  construction rather than by convention.
- Negative: relationship labels are coarser than a true identity graph
  would allow (e.g. there is no notion of *which* specific credential
  or role is used, only that a destination *is* the identity service).
  This is an accepted, documented scoping limit for this phase, not a
  claim that identity modeling is complete.

## Future reconsideration trigger

Revisit if a future phase needs to reason about specific
credentials/roles/permissions rather than asset-level relationships
(e.g. "attacker has `admin` role on `iam-service-01` but not
`super-admin`"), which would justify the first-class identity graph
rejected above as a dedicated, escalated change.
