from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.database.session import get_database_session
from app.schemas.detection import (
    AnomalyAssessmentPage,
    Classification,
    DetectionModel,
    DetectionTrainingRequest,
    DetectionTrainingResult,
    ModelEvaluation,
    RunScoringRequest,
    RunScoringResult,
)
from app.services.assessment_query_service import assessment_query_service
from app.services.detection_evaluation_service import detection_evaluation_service
from app.services.detection_scoring_service import detection_scoring_service
from app.services.detection_training_service import detection_training_service

router = APIRouter(prefix="/v1/detection", tags=["detection"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]


@router.post(
    "/models/train", response_model=DetectionTrainingResult, status_code=status.HTTP_201_CREATED
)
def train_model(
    training: DetectionTrainingRequest, request: Request, session: DatabaseSession
) -> DetectionTrainingResult:
    return detection_training_service.train(
        session, training, request.app.state.settings.model_artifact_dir
    )


@router.get("/models", response_model=list[DetectionModel])
def list_models(session: DatabaseSession) -> list[DetectionModel]:
    return detection_training_service.list_models(session)


@router.get("/models/{model_id}", response_model=DetectionModel)
def get_model(model_id: str, session: DatabaseSession) -> DetectionModel:
    return detection_training_service.get_model(session, model_id)


@router.post("/runs/{run_id}/score", response_model=RunScoringResult)
def score_run(
    run_id: str, scoring: RunScoringRequest, session: DatabaseSession
) -> RunScoringResult:
    return detection_scoring_service.score_run(
        session, run_id, scoring.model_id, scoring.force_rescore
    )


@router.get("/runs/{run_id}/assessments", response_model=AnomalyAssessmentPage)
def list_assessments(
    run_id: str,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    classification: Classification | None = None,
    minimum_anomaly_score: Annotated[float | None, Query(ge=0, le=1)] = None,
    event_type: str | None = None,
    source_id: str | None = None,
    user_id: str | None = None,
    model_id: str | None = None,
) -> AnomalyAssessmentPage:
    return assessment_query_service.query(
        session,
        run_id,
        page=page,
        page_size=page_size,
        classification=classification,
        minimum_anomaly_score=minimum_anomaly_score,
        event_type=event_type,
        source_id=source_id,
        user_id=user_id,
        model_id=model_id,
    )


@router.post("/models/{model_id}/evaluate", response_model=ModelEvaluation)
def evaluate_model(model_id: str, session: DatabaseSession) -> ModelEvaluation:
    return detection_evaluation_service.evaluate(session, model_id)


@router.get("/evaluations/{evaluation_id}", response_model=ModelEvaluation)
def get_evaluation(evaluation_id: str, session: DatabaseSession) -> ModelEvaluation:
    return detection_evaluation_service.get(session, evaluation_id)
