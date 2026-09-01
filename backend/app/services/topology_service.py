from datetime import UTC, datetime

from app.core.exceptions import ApplicationError
from app.schemas.topology import (
    InfrastructureEdge,
    InfrastructureNode,
    Neighbourhood,
    TopologySnapshot,
)
from app.services.infrastructure_service import inventory_service

TOPOLOGY_VERSION = "aegisarena-cloud-topology-v1"

NODE_DETAILS = {
    "external-user-01": (
        "external_client",
        "edge_zone",
        "public",
        "Synthetic external consumer of the public cloud API surface.",
    ),
    "api-gateway-01": (
        "api_gateway",
        "edge_zone",
        "internal",
        "Synthetic managed API gateway terminating public requests.",
    ),
    "load-balancer-01": (
        "load_balancer",
        "edge_zone",
        "internal",
        "Synthetic layer-7 load balancer distributing gateway traffic.",
    ),
    "kubernetes-cluster-01": (
        "kubernetes_control_plane",
        "cluster_zone",
        "restricted",
        "Synthetic Kubernetes control plane scheduling range workloads.",
    ),
    "worker-node-01": (
        "kubernetes_node",
        "cluster_zone",
        "restricted",
        "Synthetic Kubernetes worker node hosting range pods.",
    ),
    "auth-pod-01": (
        "kubernetes_pod",
        "workload_zone",
        "restricted",
        "Synthetic authentication pod issuing session tokens.",
    ),
    "application-pod-01": (
        "kubernetes_pod",
        "workload_zone",
        "internal",
        "Synthetic application pod serving business requests.",
    ),
    "admin-service-01": (
        "admin_service",
        "management_zone",
        "restricted",
        "Synthetic administrative control service for the cloud estate.",
    ),
    "iam-service-01": (
        "identity_service",
        "identity_zone",
        "highly_restricted",
        "Synthetic identity and access management service.",
    ),
    "cloud-database-01": (
        "database",
        "data_zone",
        "highly_restricted",
        "Synthetic managed cloud database holding sensitive records.",
    ),
    "object-storage-01": (
        "object_storage",
        "data_zone",
        "restricted",
        "Synthetic object storage bucket holding exported artefacts.",
    ),
    "monitoring-service-01": (
        "monitoring_service",
        "operations_zone",
        "internal",
        "Synthetic observability and metrics service.",
    ),
    "backup-service-01": (
        "backup_service",
        "operations_zone",
        "restricted",
        "Synthetic backup and restore service.",
    ),
}

# Declared replica counts for the synthetic workload pods, reported as node metadata.
POD_REPLICAS = {"auth-pod-01": 2, "application-pod-01": 4}

EDGE_DEFINITIONS = (
    (
        "external-user-01",
        "api-gateway-01",
        "expected_relationship",
        "HTTPS",
        True,
        "standard",
    ),
    (
        "api-gateway-01",
        "load-balancer-01",
        "expected_relationship",
        "HTTPS",
        True,
        "service",
    ),
    (
        "api-gateway-01",
        "iam-service-01",
        "expected_relationship",
        "token",
        True,
        "service",
    ),
    (
        "api-gateway-01",
        "application-pod-01",
        "conditionally_allowed_relationship",
        "HTTPS",
        True,
        "service",
    ),
    (
        "load-balancer-01",
        "kubernetes-cluster-01",
        "expected_relationship",
        "HTTPS",
        True,
        "service",
    ),
    (
        "kubernetes-cluster-01",
        "worker-node-01",
        "expected_relationship",
        "kubelet",
        True,
        "service",
    ),
    (
        "worker-node-01",
        "auth-pod-01",
        "expected_relationship",
        "pod-network",
        True,
        "service",
    ),
    (
        "worker-node-01",
        "application-pod-01",
        "expected_relationship",
        "pod-network",
        True,
        "service",
    ),
    (
        "auth-pod-01",
        "iam-service-01",
        "expected_relationship",
        "oidc",
        True,
        "service",
    ),
    (
        "auth-pod-01",
        "application-pod-01",
        "conditionally_allowed_relationship",
        "token",
        True,
        "service",
    ),
    (
        "application-pod-01",
        "cloud-database-01",
        "expected_relationship",
        "database",
        True,
        "service",
    ),
    (
        "application-pod-01",
        "object-storage-01",
        "expected_relationship",
        "storage-api",
        True,
        "service",
    ),
    (
        "application-pod-01",
        "monitoring-service-01",
        "expected_relationship",
        "metrics",
        True,
        "service",
    ),
    (
        "admin-service-01",
        "kubernetes-cluster-01",
        "expected_relationship",
        "kube-api",
        True,
        "elevated",
    ),
    (
        "admin-service-01",
        "iam-service-01",
        "expected_relationship",
        "admin-api",
        True,
        "elevated",
    ),
    (
        "iam-service-01",
        "auth-pod-01",
        "conditionally_allowed_relationship",
        "token",
        True,
        "service",
    ),
    (
        "iam-service-01",
        "admin-service-01",
        "conditionally_allowed_relationship",
        "admin-api",
        True,
        "elevated",
    ),
    (
        "cloud-database-01",
        "backup-service-01",
        "expected_relationship",
        "backup",
        True,
        "service",
    ),
    (
        "cloud-database-01",
        "monitoring-service-01",
        "expected_relationship",
        "monitoring",
        True,
        "monitoring",
    ),
    (
        "object-storage-01",
        "backup-service-01",
        "expected_relationship",
        "backup",
        True,
        "service",
    ),
    (
        "backup-service-01",
        "cloud-database-01",
        "conditionally_allowed_relationship",
        "restore",
        True,
        "service",
    ),
    (
        "monitoring-service-01",
        "iam-service-01",
        "expected_relationship",
        "monitoring",
        True,
        "monitoring",
    ),
    (
        "monitoring-service-01",
        "kubernetes-cluster-01",
        "expected_relationship",
        "monitoring",
        True,
        "monitoring",
    ),
    (
        "monitoring-service-01",
        "cloud-database-01",
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
                    "application-pod-01",
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
        metadata: dict[str, object] = {"inventory_asset_type": asset.asset_type.value}
        if asset_id in POD_REPLICAS:
            metadata["replicas"] = POD_REPLICAS[asset_id]
        return InfrastructureNode(
            asset_id=asset_id,
            display_name=asset.name,
            asset_type=asset_type,
            zone=zone,
            sensitivity=sensitivity,
            criticality=asset.criticality.value,
            description=description,
            synthetic=True,
            metadata=metadata,
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
