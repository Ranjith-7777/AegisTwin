from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_database_session
from app.schemas.blast_radius import BlastRadiusQuery, BlastRadiusResult
from app.services.blast_radius_service import blast_radius_service

router = APIRouter(prefix="/v1/blast-radius", tags=["blast-radius"])
Db = Annotated[Session, Depends(get_database_session)]


@router.post("", response_model=BlastRadiusResult)
def estimate_blast_radius(query: BlastRadiusQuery, session: Db) -> BlastRadiusResult:
    return blast_radius_service.estimate(
        session,
        query.compromised_asset_ids,
        query.simulation_run_id,
        query.through_sequence_number,
        query.max_depth,
    )
