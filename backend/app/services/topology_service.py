from datetime import UTC, datetime

from app.core.exceptions import ApplicationError
from app.schemas.topology import (
    InfrastructureEdge,
    InfrastructureNode,
    Neighbourhood,
    TopologySnapshot,
)
from app.services.infrastructure_service import inventory_service

TOPOLOGY_VERSION = "aegistwin-synthetic-topology-v1"

NODE_DETAILS = {
    "employee-laptop-01": ("endpoint", "user_zone", "internal", "Synthetic employee endpoint."),
    "administrator-workstation-01": (
        "endpoint",
        "user_zone",
        "restricted",
        "Synthetic administrative endpoint.",
    ),
    "authentication-server-01": (
        "identity_service",
        "identity_zone",
        "restricted",
        "Synthetic identity and authentication service.",
    ),
    "examination-portal-01": (
        "web_application",
        "application_zone",
        "internal",
        "Synthetic examination portal.",
    ),
    "application-server-01": (
        "application_server",
        "application_zone",
        "restricted",
        "Synthetic application processing service.",
    ),
    "examination-database-01": (
        "database",
        "data_zone",
        "highly_restricted",
        "Synthetic examination data store.",
    ),
    "backup-server-01": (
        "backup_service",
        "operations_zone",
        "restricted",
        "Synthetic backup service.",
    ),
    "monitoring-server-01": (
        "monitoring_service",
        "operations_zone",
        "internal",
        "Synthetic monitoring service.",
    ),
}

EDGE_DEFINITIONS = (
    (
        "employee-laptop-01",
        "authentication-server-01",
        "expected_relationship",
        "HTTPS",
        True,
        "standard",
    ),
    (
        "employee-laptop-01",
        "examination-portal-01",
        "expected_relationship",
        "HTTPS",
        True,
        "standard",
    ),
    (
        "administrator-workstation-01",
        "authentication-server-01",
        "expected_relationship",
        "HTTPS",
        True,
        "elevated",
    ),
    (
        "administrator-workstation-01",
        "monitoring-server-01",
        "expected_relationship",
        "monitoring",
        True,
        "elevated",
    ),
    (
        "authentication-server-01",
        "examination-portal-01",
        "expected_relationship",
        "token",
        True,
        "service",
    ),
    (
        "authentication-server-01",
        "application-server-01",
        "conditionally_allowed_relationship",
        "service",
        True,
        "service",
    ),
    (
        "examination-portal-01",
        "application-server-01",
        "expected_relationship",
        "HTTPS",
        True,
        "service",
    ),
    (
        "application-server-01",
        "examination-database-01",
        "expected_relationship",
        "database",
        True,
        "service",
    ),
    (
        "application-server-01",
        "backup-server-01",
        "conditionally_allowed_relationship",
        "backup",
        True,
        "service",
    ),
    (
        "application-server-01",
        "monitoring-server-01",
        "expected_relationship",
        "monitoring",
        True,
        "service",
    ),
    (
        "examination-database-01",
        "backup-server-01",
        "expected_relationship",
        "backup",
        True,
        "service",
    ),
    (
        "examination-database-01",
        "monitoring-server-01",
        "expected_relationship",
        "monitoring",
        True,
        "service",
    ),
    (
        "backup-server-01",
        "examination-database-01",
        "conditionally_allowed_relationship",
        "restore",
        True,
        "service",
    ),
    (
        "monitoring-server-01",
        "authentication-server-01",
        "expected_relationship",
        "monitoring",
        True,
        "monitoring",
    ),
    (
        "monitoring-server-01",
        "application-server-01",
        "expected_relationship",
        "monitoring",
        True,
        "monitoring",
    ),
    (
        "monitoring-server-01",
        "examination-database-01",
        "expected_relationship",
        "monitoring",
        True,
        "monitoring",
    ),
)


class TopologyService:
    def nodes(self, include_sink: bool = False) -> list[InfrastructureNode]:
        nodes = [self._node(asset.asset_id) for asset in inventory_service.list_assets()]
        if include_sink:
            nodes.append(self._sink())
        return nodes

    def edges(self, include_sink: bool = False) -> list[InfrastructureEdge]:
        edges = [self._edge(*item) for item in EDGE_DEFINITIONS]
        if include_sink:
            edges.append(
                self._edge(
                    "application-server-01",
                    "simulation-egress-sink-01",
                    "simulation_only_external_relationship",
                    "synthetic-web",
                    True,
                    "isolated",
                )
            )
        return edges

    def snapshot(self, include_sink: bool = False) -> TopologySnapshot:
        return TopologySnapshot(
            topology_version=TOPOLOGY_VERSION,
            nodes=self.nodes(include_sink),
            edges=self.edges(include_sink),
            generated_at=datetime.now(UTC),
            synthetic=True,
        )

    def node(self, asset_id: str, include_sink: bool = False) -> InfrastructureNode:
        match = next((item for item in self.nodes(include_sink) if item.asset_id == asset_id), None)
        if match is None:
            raise ApplicationError(
                "TOPOLOGY_ASSET_NOT_FOUND", "The synthetic topology asset was not found.", 404
            )
        return match

    def edge(
        self, source: str, destination: str, include_sink: bool = False
    ) -> InfrastructureEdge | None:
        return next(
            (
                item
                for item in self.edges(include_sink)
                if item.source_asset_id == source and item.destination_asset_id == destination
            ),
            None,
        )

    def neighbourhood(self, asset_id: str, include_sink: bool = False) -> Neighbourhood:
        node = self.node(asset_id, include_sink)
        incoming = [
            item for item in self.edges(include_sink) if item.destination_asset_id == asset_id
        ]
        outgoing = [item for item in self.edges(include_sink) if item.source_asset_id == asset_id]
        ids = sorted(
            {item.source_asset_id for item in incoming}
            | {item.destination_asset_id for item in outgoing}
        )
        return Neighbourhood(
            node=node,
            incoming_edges=incoming,
            outgoing_edges=outgoing,
            neighbours=[self.node(item, include_sink) for item in ids],
            synthetic=True,
        )

    @staticmethod
    def _node(asset_id: str) -> InfrastructureNode:
        asset = inventory_service.get_asset(asset_id)
        asset_type, zone, sensitivity, description = NODE_DETAILS[asset_id]
        return InfrastructureNode(
            asset_id=asset_id,
            display_name=asset.name,
            asset_type=asset_type,
            zone=zone,
            sensitivity=sensitivity,
            criticality=asset.criticality.value,
            description=description,
            synthetic=True,
            metadata={"inventory_asset_type": asset.asset_type.value},
        )

    @staticmethod
    def _sink() -> InfrastructureNode:
        return InfrastructureNode(
            asset_id="simulation-egress-sink-01",
            display_name="Synthetic Egress Sink 01",
            asset_type="synthetic_external_sink",
            zone="synthetic_external_zone",
            sensitivity="simulation_only",
            criticality="low",
            description="Documentation-only sink isolated to defined synthetic demonstrations.",
            synthetic=True,
            metadata={"external": False, "documentation_only": True},
        )

    @staticmethod
    def _edge(
        source: str, destination: str, relationship: str, protocol: str, permitted: bool, trust: str
    ) -> InfrastructureEdge:
        return InfrastructureEdge(
            edge_id=f"{source}--{destination}",
            source_asset_id=source,
            destination_asset_id=destination,
            relationship_type=relationship,
            protocol_label=protocol,
            direction="directed",
            permitted=permitted,
            trust_level=trust,
            synthetic=True,
            metadata={},
        )


topology_service = TopologyService()
