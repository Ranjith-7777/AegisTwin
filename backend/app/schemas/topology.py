from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

PathType = Literal["expected", "observed", "correlated", "predicted"]


class InfrastructureNode(BaseModel):
    asset_id: str
    display_name: str
    asset_type: str
    zone: str
    sensitivity: str
    criticality: str
    description: str
    synthetic: Literal[True] = True
    metadata: dict[str, object] = Field(default_factory=dict)


class InfrastructureEdge(BaseModel):
    edge_id: str
    source_asset_id: str
    destination_asset_id: str
    relationship_type: str
    protocol_label: str | None = None
    direction: Literal["directed"] = "directed"
    permitted: bool
    trust_level: str
    synthetic: Literal[True] = True
    metadata: dict[str, object] = Field(default_factory=dict)


class TopologySnapshot(BaseModel):
    topology_version: str
    nodes: list[InfrastructureNode]
    edges: list[InfrastructureEdge]
    generated_at: datetime
    synthetic: Literal[True] = True


class TopologyNodePage(BaseModel):
    items: list[InfrastructureNode]
    page: int
    page_size: int
    total: int
    pages: int
    synthetic: Literal[True] = True


class TopologyEdgePage(BaseModel):
    items: list[InfrastructureEdge]
    page: int
    page_size: int
    total: int
    pages: int
    synthetic: Literal[True] = True


class Neighbourhood(BaseModel):
    node: InfrastructureNode
    incoming_edges: list[InfrastructureEdge]
    outgoing_edges: list[InfrastructureEdge]
    neighbours: list[InfrastructureNode]
    synthetic: Literal[True] = True


class TopologyPath(BaseModel):
    path_type: PathType
    ordered_node_ids: list[str]
    ordered_edge_ids: list[str]
    path_length: int
    evidence_source: str
    through_sequence_number: int | None
    hypothetical: bool
    statement: str
    synthetic: Literal[True] = True


class TopologyPathPage(BaseModel):
    items: list[TopologyPath]
    total: int
    maximum_paths: Annotated[int, Field(ge=1, le=10)]
    synthetic: Literal[True] = True


class RunTopologyState(BaseModel):
    simulation_run_id: str
    model_id: str | None
    observed_asset_ids: list[str]
    observed_edge_ids: list[str]
    correlated_asset_ids: list[str]
    correlated_edge_ids: list[str]
    predicted_asset_ids: list[str]
    predicted_edge_ids: list[str]
    current_sequence_limit: int
    synthetic: Literal[True] = True
