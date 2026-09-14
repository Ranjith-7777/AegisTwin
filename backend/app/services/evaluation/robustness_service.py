"""Phase 5 - PM spec Section 38: the partial-observability robustness
experiment runner.

A SEPARATE capability from the canonical 4x5x4 matrix
(`batch_service.CANONICAL_SEEDS`/`CANONICAL_DEFENCE_MODES`/
`CANONICAL_SCENARIO_MATRIX`) - per the spec ("Do NOT make this part of the
default 80-run canonical matrix unless runtime is acceptable. It can be a
separate robustness experiment"), this module is never invoked by
`batch_service.BatchService.create_batch`. It is invoked explicitly, one
scenario/seed/mode combination at a time, by whichever later stage actually
runs the robustness experiment(s) for the completion report.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.models import ExperimentRecord
from app.schemas.evaluation import DefenceMode, ExperimentCreate, ExperimentStatus
from app.services.evaluation.evaluation_pipeline import evaluate_experiment
from app.services.evaluation.experiment_service import experiment_service
from app.services.evaluation.perturbation_service import PARTIAL_OBSERVABILITY_PERTURBATION_ID


def run_robustness_experiment(
    session: Session,
    scenario_id: str,
    seed: int,
    defence_mode: DefenceMode,
    hidden_fraction: float = 0.3,
    batch_id: str | None = None,
) -> tuple[ExperimentRecord, ExperimentRecord]:
    """Runs TWO experiments back-to-back with identical scenario/seed/mode:
    one unperturbed baseline and one with the Section 38 partial-
    observability perturbation applied, evaluates both (metrics/MCI/ARS
    - only for experiments that actually complete, matching
    `batch_service`'s own "never abort on a single failure" convention),
    and returns the pair `(baseline, perturbed)` for direct comparison
    (e.g. via `comparison_service`-style before/after reasoning, left to
    the caller).

    Both experiments share the same deterministic `simulation_run_id` (see
    `perturbation_service` module docstring) - that is exactly what makes
    them a fair, reproducible pair: identical attack, identical detector,
    identical defence mode, differing only in what evidence THIS
    experiment's evaluation disregards.
    """

    baseline_request = ExperimentCreate(
        scenario_id=scenario_id,
        seed=seed,
        defence_mode=defence_mode,
        label="robustness-baseline",
    )
    perturbed_request = ExperimentCreate(
        scenario_id=scenario_id,
        seed=seed,
        defence_mode=defence_mode,
        label="robustness-perturbed",
        perturbation_id=PARTIAL_OBSERVABILITY_PERTURBATION_ID,
        perturbation_params={"hidden_fraction": hidden_fraction},
    )

    baseline = experiment_service.create_and_run(session, baseline_request, batch_id=batch_id)
    if baseline.status == ExperimentStatus.COMPLETED.value:
        evaluate_experiment(session, baseline.experiment_id)

    perturbed = experiment_service.create_and_run(session, perturbed_request, batch_id=batch_id)
    if perturbed.status == ExperimentStatus.COMPLETED.value:
        evaluate_experiment(session, perturbed.experiment_id)

    return baseline, perturbed
