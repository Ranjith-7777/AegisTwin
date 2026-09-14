"""Phase 5 Stage 4: the batch runner.

Runs a requested scenario x seed x defence_mode matrix SEQUENTIALLY to
completion. Per PM spec Section 33 ("Use sequential execution initially...
The backend may execute sequentially for Phase 5. No distributed job system
is required") this deliberately does NOT introduce threading,
multiprocessing, Celery, or any background worker - a plain nested-loop
`for` over `experiment_service.create_and_run` followed by
`evaluate_experiment` is correct and matches the spec.

Per PM spec Section 88, an individual experiment's failure must not destroy
the rest of the batch: a failed `ExperimentRecord` (status="failed") or an
exception raised by `evaluate_experiment` for an otherwise-completed
experiment both simply increment `failed_count` and move on to the next
combination in the matrix.

## Canonical evaluation matrix

`CANONICAL_SEEDS` / `CANONICAL_DEFENCE_MODES` are the PM spec's Section 31/33
fixed matrix axes. `CANONICAL_SCENARIO_MATRIX` maps the PM's four named
"scenario classes" onto this codebase's actual scenario catalogue.

**Finding on the "IAM privilege escalation" class (read before changing this
mapping):** the PM spec asks whether `staged-compromise-demo` produces
ground truth genuinely distinguishable from `credential-compromise`, or
whether it is the same attack pattern in a different wrapper. Comparing
`app/services/scenario_service.py`'s two `SimulationScenario.steps` lists
directly:

- `credential-compromise` has 3 ground-truth (HIGH/CRITICAL severity) steps:
  step 4 "IAM privilege-level change" (HIGH), step 6 "Internal connection
  toward the cloud database" (HIGH), step 7 "Large synthetic outbound
  transfer" (HIGH). Its analogous "access the application pod" step (step 5)
  is severity MEDIUM - not ground truth.
- `staged-compromise-demo` has 4 ground-truth (HIGH severity) steps: step 8
  "Explicit IAM permission change" (HIGH, with `metadata={"account_manipulation":
  True, ...}` - `credential-compromise`'s analogous step carries no such
  flag), step 9 "Remote service access toward the application pod" (HIGH,
  `metadata={"remote_service": "synthetic-cloud-shell"}` - the directly
  analogous step in `credential-compromise` is severity MEDIUM and is NOT
  ground truth there), step 10 "Connection toward the cloud database"
  (HIGH), step 11 "Large outbound transfer..." (HIGH).

So the two scenarios are NOT the same ground truth wearing a different
label: `staged-compromise-demo` promotes its "application pod access" step
to a genuine HIGH-severity ground-truth attack step (with a distinct
`remote_service`/cloud-shell technique tag) and adds an explicit
`account_manipulation` flag on its privilege-change step, giving it one MORE
detectable attack step (4 vs 3) with real technique-level differences
`detection_coverage`/`false_positive_rate` will score differently. This is a
genuine, if narrow, distinction - not a fabricated 4th class - so
`staged-compromise-demo` is kept as the IAM-privilege-escalation mapping.
The limitation is real and should be stated honestly wherever this matrix is
documented: `staged-compromise-demo` and `credential-compromise` share the
same overall attack narrative (repeated failed auth -> off-hours login ->
unseen client -> IAM change -> lateral access -> exfiltration) and reuse the
same asset topology, so they are a near-family rather than two independent
attacker archetypes; the distinguishing ground truth is real but the classes
are closer to each other than the DDoS/credential-compromise/workload-
compromise trio is to any of them.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import EvaluationBatchRecord
from app.events.envelope import DomainEvent, EvaluationBatchCreatedPayload
from app.events.registry import get_event_bus
from app.events.types import EventType
from app.schemas.evaluation import DefenceMode, ExperimentCreate, ExperimentStatus
from app.services.evaluation.evaluation_pipeline import evaluate_experiment
from app.services.evaluation.experiment_service import experiment_service

# PM spec Section 33's fixed canonical matrix axes. NEVER vary these
# per-call - they exist so every canonical batch run is comparable to every
# other one.
CANONICAL_SEEDS: list[int] = [17, 42, 84, 99, 123]
CANONICAL_DEFENCE_MODES: list[DefenceMode] = [
    DefenceMode.NO_ACTIVE_DEFENCE,
    DefenceMode.RULE_BASED,
    DefenceMode.ML_ASSISTED,
    DefenceMode.AGENTIC,
]

# See the module docstring "Finding on the IAM privilege escalation class"
# for the full comparison this mapping is based on. All 4 classes are kept -
# `staged-compromise-demo` was checked against `credential-compromise` and
# found to carry genuinely distinguishable ground truth (a different
# detectable-attack-step count and distinct technique metadata), not merely
# a relabeled duplicate - but the two remain a closely related "family"
# rather than fully independent attacker archetypes, which should be stated
# honestly in any documentation/report referencing this matrix.
CANONICAL_SCENARIO_MATRIX: dict[str, str] = {
    "ddos_service_saturation": "ddos-traffic-spike",
    "credential_compromise": "credential-compromise",
    "iam_privilege_escalation": "staged-compromise-demo",
    "workload_service_compromise": "suspicious-kubernetes-pod",
}


class BatchService:
    def create_batch(
        self,
        session: Session,
        scenario_ids: list[str],
        seeds: list[int],
        defence_modes: list[DefenceMode],
        max_experiments: int | None = None,
    ) -> EvaluationBatchRecord:
        """Persists a batch record, then runs the full requested
        scenario x seed x defence_mode matrix (nested loop order:
        scenario -> seed -> mode) sequentially to completion. See module
        docstring for why this is sequential and why individual experiment
        failures do not abort the batch."""

        combinations = [
            (scenario_id, seed, mode)
            for scenario_id in scenario_ids
            for seed in seeds
            for mode in defence_modes
        ]
        total_requested = len(combinations)
        truncated = max_experiments is not None and total_requested > max_experiments
        if truncated:
            assert max_experiments is not None
            combinations = combinations[:max_experiments]

        now = datetime.now(UTC)
        batch = EvaluationBatchRecord(
            batch_id=str(uuid4()),
            scenario_ids_json=list(scenario_ids),
            seeds_json=list(seeds),
            defence_modes_json=[mode.value for mode in defence_modes],
            status="running",
            total_experiments=len(combinations),
            completed_count=0,
            failed_count=0,
            experiment_ids_json=[],
            max_experiments=max_experiments,
            truncated=truncated,
            started_at=now,
            created_at=now,
            synthetic=True,
        )
        session.add(batch)
        session.commit()
        get_event_bus().publish(
            DomainEvent(
                event_type=EventType.EVALUATION_BATCH_CREATED,
                source="evaluation",
                correlation_id=batch.batch_id,
                resource_ids=[batch.batch_id],
                payload=EvaluationBatchCreatedPayload(
                    batch_id=batch.batch_id,
                    total_experiments=batch.total_experiments,
                    scenario_ids=list(scenario_ids),
                    seeds=list(seeds),
                    defence_modes=[mode.value for mode in defence_modes],
                ),
            )
        )

        started = time.perf_counter()
        experiment_ids: list[str] = []
        completed_count = 0
        failed_count = 0

        for scenario_id, seed, mode in combinations:
            request = ExperimentCreate(scenario_id=scenario_id, seed=seed, defence_mode=mode)
            try:
                experiment = experiment_service.create_and_run(
                    session, request, batch_id=batch.batch_id
                )
            except Exception:
                # A hard failure BEFORE any `ExperimentRecord` could even be
                # created (e.g. an unknown/unsupported `scenario_id` raises
                # out of `scenario_service.get_scenario` before
                # `ExperimentService.create_and_run`'s own try/except
                # begins) - there is no experiment_id to record, but the
                # rest of the batch must still proceed.
                session.rollback()
                failed_count += 1
                batch.completed_count = completed_count
                batch.failed_count = failed_count
                session.commit()
                continue

            experiment.batch_id = batch.batch_id
            session.commit()
            experiment_ids.append(experiment.experiment_id)

            if experiment.status == ExperimentStatus.COMPLETED.value:
                try:
                    evaluate_experiment(session, experiment.experiment_id)
                    completed_count += 1
                except Exception:
                    # The experiment itself succeeded, but scoring could not
                    # be completed (e.g. missing evidence) - count it as a
                    # batch failure without touching the already-persisted
                    # ExperimentRecord's own status. Never abort the batch.
                    session.rollback()
                    failed_count += 1
            else:
                failed_count += 1

            batch.experiment_ids_json = list(experiment_ids)
            batch.completed_count = completed_count
            batch.failed_count = failed_count
            session.commit()

        runtime_seconds = round(time.perf_counter() - started, 6)

        if completed_count == 0:
            status = "failed"
        elif failed_count == 0:
            status = "completed"
        else:
            status = "completed_with_failures"

        batch.status = status
        batch.ended_at = datetime.now(UTC)
        batch.runtime_seconds = runtime_seconds
        session.commit()
        session.refresh(batch)
        return batch

    def get(self, session: Session, batch_id: str) -> EvaluationBatchRecord:
        record = session.get(EvaluationBatchRecord, batch_id)
        if record is None:
            raise ApplicationError("BATCH_NOT_FOUND", "The evaluation batch was not found.", 404)
        return record

    def list(self, session: Session) -> list[EvaluationBatchRecord]:
        statement = select(EvaluationBatchRecord).order_by(EvaluationBatchRecord.created_at.desc())
        return list(session.scalars(statement))


batch_service = BatchService()
