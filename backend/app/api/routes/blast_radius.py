from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import RequireViewer
from app.database.session import get_database_session
from app.schemas.blast_radius import BlastRadiusQuery, BlastRadiusResult
from app.services.blast_radius_service import blast_radius_service

router = APIRouter(prefix="/v1/blast-radius", tags=["blast-radius"])
Db = Annotated[Session, Depends(get_database_session)]


# NOTE: POST because the query payload (compromised_asset_ids, etc.) doesn't
# fit cleanly in query params, but this is a pure read/what-if computation
# with no persisted side effects, so it is classified VIEWER like the other
# read-only graph/topology endpoints.
@router.post("", response_model=BlastRadiusResult, dependencies=[RequireViewer])
def estimate_blast_radius(query: BlastRadiusQuery, session: Db) -> BlastRadiusResult:
    return blast_radius_service.estimate(
        session,
        query.compromised_asset_ids,
        query.simulation_run_id,
        query.through_sequence_number,
        query.max_depth,
    )
