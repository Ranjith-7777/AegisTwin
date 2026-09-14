from fastapi import APIRouter

from app.api.routes import (
    agents,
    attack_graph,
    autonomy,
    blast_radius,
    blue_planning,
    correlation,
    detection,
    evaluation,
    health,
    mitre,
    orchestration,
    policy,
    prediction,
    purple,
    response,
    safety,
    simulation,
    system,
    telemetry,
    topology,
    workflow,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(system.router)
api_router.include_router(safety.router)
api_router.include_router(simulation.router)
api_router.include_router(telemetry.router)
api_router.include_router(detection.router)
api_router.include_router(correlation.router)
api_router.include_router(prediction.router)
api_router.include_router(mitre.router)
api_router.include_router(topology.router)
api_router.include_router(response.router)
api_router.include_router(orchestration.router)
api_router.include_router(attack_graph.router)
api_router.include_router(blast_radius.router)
api_router.include_router(purple.router)
api_router.include_router(agents.router)
api_router.include_router(policy.router)
api_router.include_router(autonomy.router)
api_router.include_router(blue_planning.router)
api_router.include_router(workflow.router)
api_router.include_router(evaluation.router)
