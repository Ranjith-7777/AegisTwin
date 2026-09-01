from app.schemas.simulation import AssetType, InfrastructureAsset
from app.schemas.telemetry import Severity


class InfrastructureInventoryService:
    """Read-only inventory of the synthetic AegisArena cloud estate."""

    def __init__(self) -> None:
        self._assets = (
            InfrastructureAsset(
                asset_id="external-user-01",
                name="External User",
                asset_type=AssetType.WORKSTATION,
                ip_address="192.0.2.10",
                criticality=Severity.LOW,
                relationships=("api-gateway-01",),
            ),
            InfrastructureAsset(
                asset_id="api-gateway-01",
                name="API Gateway",
                asset_type=AssetType.SERVICE,
                ip_address="198.51.100.10",
                criticality=Severity.HIGH,
                relationships=("load-balancer-01", "iam-service-01"),
            ),
            InfrastructureAsset(
                asset_id="load-balancer-01",
                name="Load Balancer",
                asset_type=AssetType.SERVICE,
                ip_address="198.51.100.20",
                criticality=Severity.HIGH,
                relationships=("kubernetes-cluster-01",),
            ),
            InfrastructureAsset(
                asset_id="kubernetes-cluster-01",
                name="Kubernetes Cluster",
                asset_type=AssetType.SERVER,
                ip_address="198.51.100.30",
                criticality=Severity.CRITICAL,
                relationships=("worker-node-01",),
            ),
            InfrastructureAsset(
                asset_id="worker-node-01",
                name="Worker Node",
                asset_type=AssetType.SERVER,
                ip_address="198.51.100.40",
                criticality=Severity.HIGH,
                relationships=("auth-pod-01", "application-pod-01"),
            ),
            InfrastructureAsset(
                asset_id="auth-pod-01",
                name="Auth Pod",
                asset_type=AssetType.SERVICE,
                ip_address="198.51.100.50",
                criticality=Severity.HIGH,
                relationships=("iam-service-01",),
            ),
            InfrastructureAsset(
                asset_id="application-pod-01",
                name="Application Pod",
                asset_type=AssetType.SERVER,
                ip_address="198.51.100.60",
                criticality=Severity.HIGH,
                relationships=("cloud-database-01", "object-storage-01"),
            ),
            InfrastructureAsset(
                asset_id="admin-service-01",
                name="Admin Service",
                asset_type=AssetType.SERVICE,
                ip_address="198.51.100.70",
                criticality=Severity.HIGH,
                relationships=("kubernetes-cluster-01", "iam-service-01"),
            ),
            InfrastructureAsset(
                asset_id="iam-service-01",
                name="IAM Service",
                asset_type=AssetType.SERVICE,
                ip_address="198.51.100.80",
                criticality=Severity.CRITICAL,
                relationships=("auth-pod-01",),
            ),
            InfrastructureAsset(
                asset_id="cloud-database-01",
                name="Cloud Database",
                asset_type=AssetType.DATABASE,
                ip_address="203.0.113.10",
                criticality=Severity.CRITICAL,
                relationships=("backup-service-01", "monitoring-service-01"),
            ),
            InfrastructureAsset(
                asset_id="object-storage-01",
                name="Object Storage",
                asset_type=AssetType.SERVICE,
                ip_address="203.0.113.20",
                criticality=Severity.HIGH,
                relationships=("backup-service-01",),
            ),
            InfrastructureAsset(
                asset_id="monitoring-service-01",
                name="Monitoring",
                asset_type=AssetType.SERVICE,
                ip_address="203.0.113.30",
                criticality=Severity.MEDIUM,
                relationships=(
                    "iam-service-01",
                    "application-pod-01",
                    "cloud-database-01",
                ),
            ),
            InfrastructureAsset(
                asset_id="backup-service-01",
                name="Backup",
                asset_type=AssetType.SERVICE,
                ip_address="203.0.113.40",
                criticality=Severity.HIGH,
                relationships=("cloud-database-01",),
            ),
        )
        self._by_id = {asset.asset_id: asset for asset in self._assets}

    def list_assets(self) -> list[InfrastructureAsset]:
        return list(self._assets)

    def get_asset(self, asset_id: str) -> InfrastructureAsset:
        return self._by_id[asset_id]

    def get_ip(self, asset_id: str | None) -> str | None:
        if asset_id is None:
            return None
        asset = self._by_id.get(asset_id)
        return asset.ip_address if asset else None


inventory_service = InfrastructureInventoryService()
