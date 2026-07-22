from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_database_session
from app.schemas.correlation import MitreTechnique
from app.services.mitre_catalogue_service import mitre_catalogue_service

router = APIRouter(prefix="/v1/mitre", tags=["mitre"])
Db = Annotated[Session, Depends(get_database_session)]


@router.get("/techniques", response_model=list[MitreTechnique])
def techniques(session: Db) -> list[MitreTechnique]:
    return mitre_catalogue_service.list(session)


@router.get("/techniques/{technique_id}", response_model=MitreTechnique)
def technique(technique_id: str, session: Db) -> MitreTechnique:
    return mitre_catalogue_service.get(session, technique_id)
