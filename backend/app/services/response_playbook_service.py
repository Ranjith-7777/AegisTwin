from app.core.exceptions import ApplicationError
from app.schemas.response import DefensivePlaybook

CATALOGUE_VERSION = "aegisarena-blue-agent-playbooks-v1"


def _playbook(
    playbook_id: str,
    name: str,
    description: str,
    action_type: str,
    targets: list[str],
    evidence: list[str],
    mutation: dict[str, object],
    reversibility: str,
    impact: str,
    blast: str,
    tier: str,
    eligible: bool,
    resource_cost: float,
    sla_sensitivity: float,
) -> DefensivePlaybook:
    return DefensivePlaybook(
        playbook_id=playbook_id,
        playbook_version="1.0",
        name=name,
        description=description,
        action_type=action_type,
        supported_target_types=targets,
        required_evidence=evidence,
        disqualifying_conditions=["target absent from causal evidence"],
        topology_mutation_specification=mutation,
        reversibility=reversibility,
        default_operational_impact=impact,
        default_blast_radius=blast,
        approval_tier=tier,
        automatic_eligibility=eligible,
        synthetic=True,
        catalogue_version=CATALOGUE_VERSION,
        resource_cost_weight=resource_cost,
        sla_sensitivity_weight=sla_sensitivity,
    )


# Positional order is contractual: ResponseService selects playbooks by index.
PLAYBOOKS = (
    _playbook(
        "increase-synthetic-monitoring",
        "Increase telemetry on the cloud asset",
        "Raises observation depth on an evidenced synthetic cloud asset without changing traffic.",
        "observe",
        ["asset"],
        ["causal asset evidence"],
        {"operation": "annotate_node"},
        "reversible",
        "low",
        "single_asset",
        "automatic_candidate",
        True,
        0.04,
        0.00,
    ),
    _playbook(
        "revoke-synthetic-sessions",
        "Revoke leaked credential sessions",
        "Models invalidation of every active session issued to an evidenced synthetic identity.",
        "session_restriction",
        ["user"],
        ["user-related evidence"],
        {"operation": "annotate_identity"},
        "reversible",
        "medium",
        "single_identity",
        "analyst_approval",
        False,
        0.06,
        0.04,
    ),
    _playbook(
        "restrict-synthetic-account",
        "Restrict IAM role bindings",
        "Models reduced IAM privilege for an evidenced synthetic service account or identity.",
        "privilege_restriction",
        ["user"],
        ["privilege or account evidence"],
        {"operation": "annotate_identity"},
        "reversible",
        "medium",
        "single_identity",
        "analyst_approval",
        False,
        0.07,
        0.05,
    ),
    _playbook(
        "isolate-synthetic-endpoint",
        "Isolate the external client",
        "Removes external client relationships only inside a cloned synthetic cloud topology.",
        "node_isolation",
        ["external_client"],
        ["involved external client"],
        {"operation": "remove_incident_edges"},
        "reversible",
        "medium",
        "single_asset",
        "analyst_approval",
        False,
        0.08,
        0.10,
    ),
    _playbook(
        "block-synthetic-route",
        "Block the network route",
        "Disables one evidenced relationship inside a cloned synthetic cloud topology.",
        "edge_restriction",
        ["relationship"],
        ["observed, correlated, or predicted relationship"],
        {"operation": "remove_edge"},
        "reversible",
        "medium",
        "single_relationship",
        "analyst_approval",
        False,
        0.05,
        0.08,
    ),
    _playbook(
        "quarantine-synthetic-application",
        "Quarantine the suspicious pod",
        "Cordons an evidenced synthetic Kubernetes pod inside a cloned topology only.",
        "node_isolation",
        ["kubernetes_pod"],
        ["involved workload pod"],
        {"operation": "remove_incident_edges"},
        "reversible",
        "high",
        "service",
        "administrator_approval",
        False,
        0.14,
        0.18,
    ),
    _playbook(
        "snapshot-synthetic-workload",
        "Snapshot the workload state",
        "Creates a metadata-only evidence snapshot for an evidenced synthetic workload.",
        "metadata_snapshot",
        ["asset"],
        ["causal asset evidence"],
        {"operation": "no_connectivity_change"},
        "reversible",
        "low",
        "single_asset",
        "analyst_approval",
        False,
        0.09,
        0.00,
    ),
    _playbook(
        "protect-sensitive-synthetic-database",
        "Shield the cloud database",
        "Restricts inbound relationships to an evidenced sensitive data store in a clone.",
        "database_protection",
        ["database", "object_storage"],
        ["data store evidence or prediction"],
        {"operation": "remove_inbound_edges"},
        "reversible",
        "high",
        "service",
        "administrator_approval",
        False,
        0.12,
        0.22,
    ),
    _playbook(
        "rate-limit-synthetic-gateway",
        "Apply gateway rate limiting",
        "Models an adaptive request-rate limit on an evidenced synthetic edge service.",
        "traffic_shaping",
        ["api_gateway", "load_balancer"],
        ["volumetric or saturation evidence"],
        {"operation": "annotate_node"},
        "reversible",
        "medium",
        "service",
        "analyst_approval",
        False,
        0.10,
        0.06,
    ),
    # Phase 4: the one real-containment playbook eligible for full automation.
    # Deliberately narrow: it only ever targets a *single, already-anomalous,
    # externally-sourced ingress relationship* (see response_service.analyze()'s
    # target-generation rule) - never an interior lateral-movement edge, never a
    # user/identity, never a database/object store. Removing one attacker's
    # ingress edge has low genuine operational cost (no legitimate traffic is
    # known to depend on a source the system has already flagged anomalous) and
    # is fully reversible, so autonomy_mode == AUTONOMOUS may execute it without
    # a human once policy_service confirms every applicable check passes - see
    # docs/architecture/AUTONOMY_MODEL.md "The one autonomous containment action".
    _playbook(
        "quarantine-synthetic-ingress-edge",
        "Quarantine the attacker's ingress route",
        "Removes one evidenced, anomalous external-to-internal ingress relationship inside a "
        "cloned synthetic cloud topology - the specific route the attacker was observed "
        "entering through, not a general interior relationship.",
        "edge_restriction",
        ["relationship"],
        ["observed anomalous external ingress relationship"],
        {"operation": "remove_edge"},
        "reversible",
        "low",
        "single_relationship",
        "automatic_candidate",
        True,
        0.05,
        0.02,
    ),
)


class ResponsePlaybookService:
    def list(self) -> list[DefensivePlaybook]:
        return list(PLAYBOOKS)

    def get(self, playbook_id: str) -> DefensivePlaybook:
        match = next((item for item in PLAYBOOKS if item.playbook_id == playbook_id), None)
        if match is None:
            raise ApplicationError(
                "RESPONSE_PLAYBOOK_NOT_FOUND", "The synthetic playbook was not found.", 404
            )
        return match


response_playbook_service = ResponsePlaybookService()
