from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.database.session import get_database_session
from app.schemas.purple import (
    PurpleTeamExperiment,
    PurpleTeamExperimentCreate,
    RedScenarioSummary,
)
from app.services.purple_team_service import purple_team_service

router = APIRouter(prefix="/v1/purple-team", tags=["purple-team"])
Db = Annotated[Session, Depends(get_database_session)]


@router.get("/scenarios", response_model=list[RedScenarioSummary])
def list_scenarios(session: Db) -> list[RedScenarioSummary]:
    return purple_team_service.list_scenarios(session)


@router.post(
    "/experiments", response_model=PurpleTeamExperiment, status_code=status.HTTP_201_CREATED
)
def run_experiment(
    experiment: PurpleTeamExperimentCreate, request: Request, session: Db
) -> PurpleTeamExperiment:
    return purple_team_service.run_experiment(
        session, experiment, request.app.state.settings.model_artifact_dir
    )


@router.get("/experiments", response_model=list[PurpleTeamExperiment])
def list_experiments(session: Db) -> list[PurpleTeamExperiment]:
    return purple_team_service.list_experiments(session)


@router.get("/experiments/{experiment_id}", response_model=PurpleTeamExperiment)
def get_experiment(experiment_id: str, session: Db) -> PurpleTeamExperiment:
    return purple_team_service.get_experiment(session, experiment_id)
