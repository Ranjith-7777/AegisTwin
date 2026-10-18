"""Create the lookup indexes the ORM declares but earlier migrations omitted.

`alembic check` reported drift: models declare `index=True` on foreign-key
style lookup columns (run, model, incident, orchestration ids) that no
migration ever created, so migrated databases (including PostgreSQL in
Azure) did full scans for every per-run query. `ix_technique_run` is dropped
because it duplicates `ix_technique_observations_simulation_run_id`.
Indexes only - no data changes.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "20261007_0018"
down_revision: Union[str, None] = "20260916_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXES: tuple[tuple[str, str, list[str], bool], ...] = (
    ("ix_agent_decisions_orchestration_id", "agent_decisions", ["orchestration_id"], False),
    ("ix_approval_requests_orchestration_id", "approval_requests", ["orchestration_id"], False),
    ("ix_audit_events_orchestration_id", "audit_events", ["orchestration_id"], False),
    (
        "ix_incident_candidate_snapshots_incident_candidate_id",
        "incident_candidate_snapshots",
        ["incident_candidate_id"],
        False,
    ),
    ("ix_incident_candidates_correlation_state", "incident_candidates", ["correlation_state"], False),
    ("ix_incident_candidates_model_id", "incident_candidates", ["model_id"], False),
    ("ix_incident_candidates_priority", "incident_candidates", ["priority"], False),
    ("ix_incident_candidates_simulation_run_id", "incident_candidates", ["simulation_run_id"], False),
    ("ix_incident_evidence_event_id", "incident_evidence", ["event_id"], False),
    (
        "ix_incident_evidence_incident_candidate_id",
        "incident_evidence",
        ["incident_candidate_id"],
        False,
    ),
    (
        "ix_prediction_evaluations_simulation_run_id",
        "prediction_evaluations",
        ["simulation_run_id"],
        False,
    ),
    (
        "ix_prediction_hypotheses_prediction_snapshot_id",
        "prediction_hypotheses",
        ["prediction_snapshot_id"],
        False,
    ),
    (
        "ix_prediction_snapshots_incident_candidate_id",
        "prediction_snapshots",
        ["incident_candidate_id"],
        False,
    ),
    ("ix_prediction_snapshots_model_id", "prediction_snapshots", ["model_id"], False),
    ("ix_prediction_snapshots_simulation_run_id", "prediction_snapshots", ["simulation_run_id"], False),
    (
        "ix_response_analyses_incident_candidate_id",
        "response_analyses",
        ["incident_candidate_id"],
        False,
    ),
    ("ix_response_analyses_model_id", "response_analyses", ["model_id"], False),
    ("ix_response_analyses_simulation_run_id", "response_analyses", ["simulation_run_id"], False),
    (
        "ix_response_impact_simulations_recommendation_id",
        "response_impact_simulations",
        ["recommendation_id"],
        True,
    ),
    (
        "ix_response_impact_simulations_simulation_run_id",
        "response_impact_simulations",
        ["simulation_run_id"],
        False,
    ),
    (
        "ix_response_orchestrations_incident_candidate_id",
        "response_orchestrations",
        ["incident_candidate_id"],
        False,
    ),
    ("ix_response_orchestrations_model_id", "response_orchestrations", ["model_id"], False),
    (
        "ix_response_orchestrations_simulation_run_id",
        "response_orchestrations",
        ["simulation_run_id"],
        False,
    ),
    ("ix_response_plan_steps_orchestration_id", "response_plan_steps", ["orchestration_id"], False),
    (
        "ix_response_recommendations_response_analysis_id",
        "response_recommendations",
        ["response_analysis_id"],
        False,
    ),
    (
        "ix_response_recommendations_simulation_run_id",
        "response_recommendations",
        ["simulation_run_id"],
        False,
    ),
    (
        "ix_response_verifications_orchestration_id",
        "response_verifications",
        ["orchestration_id"],
        False,
    ),
    (
        "ix_synthetic_executions_orchestration_id",
        "synthetic_executions",
        ["orchestration_id"],
        False,
    ),
    ("ix_technique_observations_event_id", "technique_observations", ["event_id"], False),
    ("ix_technique_observations_model_id", "technique_observations", ["model_id"], False),
    (
        "ix_technique_observations_simulation_run_id",
        "technique_observations",
        ["simulation_run_id"],
        False,
    ),
    ("ix_technique_observations_technique_id", "technique_observations", ["technique_id"], False),
)


def upgrade() -> None:
    op.drop_index("ix_technique_run", table_name="technique_observations")
    for name, table, columns, unique in INDEXES:
        op.create_index(name, table, columns, unique=unique)


def downgrade() -> None:
    for name, table, _columns, _unique in reversed(INDEXES):
        op.drop_index(name, table_name=table)
    op.create_index("ix_technique_run", "technique_observations", ["simulation_run_id"])
