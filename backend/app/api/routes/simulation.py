from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_database_session
from app.schemas.simulation import (
    InfrastructureAsset,
    SimulationRun,
    SimulationRunCreate,
    SimulationScenario,
)
from app.services.infrastructure_service import inventory_service
from app.services.scenario_service import scenario_service
from app.services.simulation_service import simulation_run_service

router = APIRouter(prefix="/v1/simulation", tags=["simulation"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]


@router.get("/infrastructure", response_model=list[InfrastructureAsset])
def list_infrastructure() -> list[InfrastructureAsset]:
    return inventory_service.list_assets()


@router.get("/scenarios", response_model=list[SimulationScenario])
def list_scenarios(session: DatabaseSession) -> list[SimulationScenario]:
    return scenario_service.list_scenarios(session)


@router.get("/scenarios/{scenario_id}", response_model=SimulationScenario)
def get_scenario(scenario_id: str, session: DatabaseSession) -> SimulationScenario:
    return scenario_service.get_scenario(session, scenario_id)


@router.post("/runs", response_model=SimulationRun, status_code=status.HTTP_201_CREATED)
def create_run(request: SimulationRunCreate, session: DatabaseSession) -> SimulationRun:
    return simulation_run_service.create_run(session, request)


@router.get("/runs", response_model=list[SimulationRun])
def list_runs(session: DatabaseSession) -> list[SimulationRun]:
    return simulation_run_service.list_runs(session)


@router.get("/runs/{run_id}", response_model=SimulationRun)
def get_run(run_id: str, session: DatabaseSession) -> SimulationRun:
    return simulation_run_service.get_run(session, run_id)
