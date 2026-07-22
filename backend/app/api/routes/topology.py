from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_database_session
from app.schemas.topology import (
    InfrastructureNode,
    Neighbourhood,
    RunTopologyState,
    TopologyEdgePage,
    TopologyNodePage,
    TopologyPathPage,
    TopologySnapshot,
)
from app.services.topology_path_service import topology_path_service
from app.services.topology_service import topology_service

router = APIRouter(prefix="/v1/topology", tags=["topology"])
Db = Annotated[Session, Depends(get_database_session)]


@router.get("", response_model=TopologySnapshot)
def topology(include_synthetic_sink: bool = False) -> TopologySnapshot:
    return topology_service.snapshot(include_synthetic_sink)


@router.get("/nodes", response_model=TopologyNodePage)
def nodes(
    page: Annotated[int, Query(ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=100)] = 50
) -> TopologyNodePage:
    items = topology_service.nodes()
    return TopologyNodePage(
        items=items[(page - 1) * page_size : page * page_size],
        page=page,
        page_size=page_size,
        total=len(items),
        pages=(len(items) + page_size - 1) // page_size,
        synthetic=True,
    )


@router.get("/nodes/{asset_id}", response_model=InfrastructureNode)
def node(asset_id: str) -> InfrastructureNode:
    return topology_service.node(asset_id)


@router.get("/edges", response_model=TopologyEdgePage)
def edges(
    page: Annotated[int, Query(ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=100)] = 50
) -> TopologyEdgePage:
    items = topology_service.edges()
    return TopologyEdgePage(
        items=items[(page - 1) * page_size : page * page_size],
        page=page,
        page_size=page_size,
        total=len(items),
        pages=(len(items) + page_size - 1) // page_size,
        synthetic=True,
    )


@router.get("/nodes/{asset_id}/neighbours", response_model=Neighbourhood)
def neighbours(asset_id: str) -> Neighbourhood:
    return topology_service.neighbourhood(asset_id)


@router.get("/paths", response_model=TopologyPathPage)
def paths(
    source_asset_id: str,
    destination_asset_id: str,
    session: Db,
    path_type: Literal["expected", "observed", "correlated", "predicted"] = "expected",
    simulation_run_id: str | None = None,
    model_id: str | None = None,
    through_sequence_number: Annotated[int | None, Query(ge=1)] = None,
    maximum_paths: Annotated[int, Query(ge=1, le=10)] = 3,
) -> TopologyPathPage:
    items = topology_path_service.paths(
        session,
        source_asset_id,
        destination_asset_id,
        path_type,
        simulation_run_id,
        model_id,
        through_sequence_number,
        maximum_paths,
    )
    return TopologyPathPage(
        items=items, total=len(items), maximum_paths=maximum_paths, synthetic=True
    )


@router.get("/runs/{run_id}/state", response_model=RunTopologyState)
def run_state(
    run_id: str,
    session: Db,
    model_id: str | None = None,
    through_sequence_number: Annotated[int | None, Query(ge=1)] = None,
) -> RunTopologyState:
    return topology_path_service.run_state(session, run_id, model_id, through_sequence_number)
