from app.schemas.simulation import AssetType, InfrastructureAsset
from app.schemas.telemetry import Severity


class InfrastructureInventoryService:
    """Read-only inventory of documentation-range, synthetic assets."""

    def __init__(self) -> None:
        self._assets = (
            InfrastructureAsset(
                asset_id="employee-laptop-01",
                name="Employee Laptop 01",
                asset_type=AssetType.WORKSTATION,
                ip_address="192.0.2.10",
                criticality=Severity.LOW,
                relationships=("authentication-server-01", "examination-portal-01"),
            ),
            InfrastructureAsset(
                asset_id="administrator-workstation-01",
                name="Administrator Workstation 01",
                asset_type=AssetType.WORKSTATION,
                ip_address="192.0.2.20",
                criticality=Severity.MEDIUM,
                relationships=("authentication-server-01", "monitoring-server-01"),
            ),
            InfrastructureAsset(
                asset_id="authentication-server-01",
                name="Authentication Server 01",
                asset_type=AssetType.SERVER,
                ip_address="198.51.100.10",
                criticality=Severity.HIGH,
                relationships=("examination-portal-01", "application-server-01"),
            ),
            InfrastructureAsset(
                asset_id="examination-portal-01",
                name="Examination Portal 01",
                asset_type=AssetType.SERVICE,
                ip_address="198.51.100.20",
                criticality=Severity.HIGH,
                relationships=("application-server-01",),
            ),
            InfrastructureAsset(
                asset_id="application-server-01",
                name="Application Server 01",
                asset_type=AssetType.SERVER,
                ip_address="198.51.100.30",
                criticality=Severity.HIGH,
                relationships=("examination-database-01", "monitoring-server-01"),
            ),
            InfrastructureAsset(
                asset_id="examination-database-01",
                name="Examination Database 01",
                asset_type=AssetType.DATABASE,
                ip_address="203.0.113.10",
                criticality=Severity.CRITICAL,
                relationships=("backup-server-01", "monitoring-server-01"),
            ),
            InfrastructureAsset(
                asset_id="backup-server-01",
                name="Backup Server 01",
                asset_type=AssetType.SERVER,
                ip_address="203.0.113.20",
                criticality=Severity.HIGH,
                relationships=("examination-database-01",),
            ),
            InfrastructureAsset(
                asset_id="monitoring-server-01",
                name="Monitoring Server 01",
                asset_type=AssetType.SERVER,
                ip_address="203.0.113.30",
                criticality=Severity.MEDIUM,
                relationships=(
                    "authentication-server-01",
                    "application-server-01",
                    "examination-database-01",
                ),
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
