"""Shared synthetic-mutation primitive, reused by both Phase 4's Synthetic
Execution Agent (`orchestration_agents.SyntheticExecutionAgent`) and Phase 5's
non-agentic evaluation baselines (`app.services.evaluation.strategies`).

`compute_mutation` answers exactly one question: "given this synthetic
playbook + target, what topology mutation results?" It is pure
topology/playbook-spec arithmetic - no agent decision-making (no policy
check, no approval routing, no persistence) - so it is genuinely
evaluation-neutral: Phase 5's "dumb" Rule-Based/ML-Assisted baselines are
entitled to call it directly, the same way `SyntheticExecutionAgent.mutation()`
does, WITHOUT going through any of Phase 4's six-agent orchestration
pipeline (Response Planner, Impact Simulation, Safety Governor, Approval
Router, Synthetic Execution, Verification) or persisting an
`AgentDecisionRecord`.

This module was extracted, unchanged in behaviour, from
`SyntheticExecutionAgent.mutation()` so there is exactly one implementation
of this arithmetic - Phase 4's agent and Phase 5's baselines can never drift
apart on methodology. `SyntheticExecutionAgent.mutation()` is now a thin
wrapper that unpacks the three scalar fields it needs
(`playbook_id`/`target_id`/`target_type`) from a `ResponseRecommendationRecord`
and delegates here.
"""

from __future__ import annotations

from app.services.response_playbook_service import response_playbook_service
from app.services.topology_service import topology_service


def compute_mutation(
    playbook_id: str, target_id: str, target_type: str
) -> tuple[list[str], list[str], dict[str, object]]:
    """The low-level "given this synthetic playbook + target, what synthetic
    mutation results?" primitive. Reads only the playbook's declared
    `topology_mutation_specification["operation"]` and the current synthetic
    topology edges - no ORM record, no session, no persistence."""

    playbook = response_playbook_service.get(playbook_id)
    operation = str(playbook.topology_mutation_specification["operation"])
    edges = topology_service.edges(True)
    changed_nodes: list[str] = []
    changed_edges: list[str] = []
    if operation == "remove_edge":
        changed_edges = [target_id]
    elif operation == "remove_inbound_edges":
        changed_nodes = [target_id]
        changed_edges = [e.edge_id for e in edges if e.destination_asset_id == target_id]
    elif operation == "remove_incident_edges":
        changed_nodes = [target_id]
        changed_edges = [
            e.edge_id for e in edges if target_id in {e.source_asset_id, e.destination_asset_id}
        ]
    elif target_type != "user":
        changed_nodes = [target_id]
    return (
        sorted(changed_nodes),
        sorted(changed_edges),
        {"operation": operation, "scope": "persisted synthetic operational state only"},
    )
