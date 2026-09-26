from fastapi import APIRouter

from app.core.auth import RequireViewer
from app.schemas.policy import PolicyDefinition
from app.services import policy_service

router = APIRouter(prefix="/v1/policies", tags=["policy"])


@router.get("", response_model=list[PolicyDefinition], dependencies=[RequireViewer])
def list_policies() -> list[PolicyDefinition]:
    return policy_service.catalogue()
