from app.core.exceptions import ApplicationError
from app.schemas.response import DefensivePlaybook

CATALOGUE_VERSION = "synthetic-defensive-playbooks-v1"


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
    )


PLAYBOOKS = (
    _playbook(
        "increase-synthetic-monitoring",
        "Increase synthetic monitoring",
        "Adds enhanced observation metadata to an evidenced synthetic asset.",
        "observe",
        ["asset"],
        ["causal asset evidence"],
        {"operation": "annotate_node"},
        "reversible",
        "low",
        "single_asset",
        "automatic_candidate",
        True,
    ),
    _playbook(
        "revoke-synthetic-sessions",
        "Revoke synthetic active sessions",
        "Models invalidation of sessions belonging to an evidenced synthetic user.",
        "session_restriction",
        ["user"],
        ["user-related evidence"],
        {"operation": "annotate_identity"},
        "reversible",
        "medium",
        "single_identity",
        "analyst_approval",
        False,
    ),
    _playbook(
        "restrict-synthetic-account",
        "Restrict synthetic account permissions",
        "Models reduced privilege for an evidenced synthetic account.",
        "privilege_restriction",
        ["user"],
        ["privilege or account evidence"],
        {"operation": "annotate_identity"},
        "reversible",
        "medium",
        "single_identity",
        "analyst_approval",
        False,
    ),
    _playbook(
        "isolate-synthetic-endpoint",
        "Isolate synthetic endpoint",
        "Removes endpoint relationships only inside a cloned synthetic topology.",
        "node_isolation",
        ["endpoint"],
        ["involved endpoint"],
        {"operation": "remove_incident_edges"},
        "reversible",
        "medium",
        "single_asset",
        "analyst_approval",
        False,
    ),
    _playbook(
        "block-synthetic-route",
        "Block synthetic source route",
        "Disables one evidenced relationship inside a cloned synthetic topology.",
        "edge_restriction",
        ["relationship"],
        ["observed, correlated, or predicted relationship"],
        {"operation": "remove_edge"},
        "reversible",
        "medium",
        "single_relationship",
        "analyst_approval",
        False,
    ),
    _playbook(
        "quarantine-synthetic-application",
        "Quarantine synthetic application service",
        "Restricts relationships of an evidenced synthetic application service in a clone.",
        "node_isolation",
        ["application_server"],
        ["involved application service"],
        {"operation": "remove_incident_edges"},
        "reversible",
        "high",
        "service",
        "administrator_approval",
        False,
    ),
    _playbook(
        "snapshot-synthetic-workload",
        "Snapshot synthetic workload state",
        "Creates a metadata-only evidence snapshot for an evidenced workload.",
        "metadata_snapshot",
        ["asset"],
        ["causal asset evidence"],
        {"operation": "no_connectivity_change"},
        "reversible",
        "low",
        "single_asset",
        "analyst_approval",
        False,
    ),
    _playbook(
        "protect-sensitive-synthetic-database",
        "Protect sensitive synthetic database",
        "Restricts inbound relationships to an evidenced sensitive database in a clone.",
        "database_protection",
        ["database"],
        ["database evidence or prediction"],
        {"operation": "remove_inbound_edges"},
        "reversible",
        "high",
        "service",
        "administrator_approval",
        False,
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
