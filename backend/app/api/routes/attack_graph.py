from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_database_session
from app.schemas.attack_graph import AttackPathAnalysisResult, AttackPathType
from app.services.attack_graph_service import attack_graph_service

router = APIRouter(prefix="/v1/attack-graph", tags=["attack-graph"])
Db = Annotated[Session, Depends(get_database_session)]


@router.get("/paths", response_model=AttackPathAnalysisResult)
def analyze_paths(
    session: Db,
    source_asset_id: str,
    path_type: AttackPathType = AttackPathType.POTENTIAL,
    target_asset_id: str | None = None,
    simulation_run_id: str | None = None,
    model_id: str | None = None,
    through_sequence_number: Annotated[int | None, Query(ge=1)] = None,
    max_depth: Annotated[int, Query(ge=1, le=10)] = 6,
    max_paths: Annotated[int, Query(ge=1, le=10)] = 5,
) -> AttackPathAnalysisResult:
    return attack_graph_service.analyze(
        session,
        source_asset_id,
        target_asset_id,
        path_type,
        simulation_run_id,
        model_id,
        through_sequence_number,
        max_depth,
        max_paths,
    )
