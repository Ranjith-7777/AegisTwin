from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import (
    PredictionEvaluationRecord,
    PredictionHypothesisRecord,
    PredictionSnapshotRecord,
    SimulationRunRecord,
)
from app.schemas.prediction import PredictionEvaluation
from app.services.prediction_service import PREDICTOR_VERSION
from app.services.prediction_truth_service import STAGED_DEMO_TRUTH, TRUTH_MANIFEST_VERSION

EVAL_NAMESPACE = UUID("3644adbc-0c03-486d-92d7-c98571d84933")


class PredictionEvaluationService:
    def evaluate(self, session: Session, run_id: str, model_id: str) -> PredictionEvaluation:
        run = session.get(SimulationRunRecord, run_id)
        if run is None:
            raise ApplicationError(
                "SIMULATION_RUN_NOT_FOUND", "The simulation run was not found.", 404
            )
        if run.scenario_id != "staged-compromise-demo":
            raise ApplicationError(
                "PREDICTION_TRUTH_UNAVAILABLE",
                "Evaluation truth is available only for the synthetic staged demonstration.",
                409,
            )
        snapshots = {
            item.through_sequence_number: item
            for item in session.scalars(
                select(PredictionSnapshotRecord).where(
                    PredictionSnapshotRecord.simulation_run_id == run_id,
                    PredictionSnapshotRecord.model_id == model_id,
                    PredictionSnapshotRecord.predictor_version == PREDICTOR_VERSION,
                )
            )
        }
        if not snapshots:
            raise ApplicationError(
                "PREDICTIONS_NOT_READY", "Prediction analysis must complete before evaluation.", 409
            )
        reciprocal: list[float] = []
        top1 = top3 = tactic_hits = asset1 = asset3 = objective_hits = covered = 0
        leads: list[int] = []
        for sequence, truth in STAGED_DEMO_TRUTH.items():
            snapshot = snapshots.get(sequence)
            if snapshot is None:
                continue
            rows = list(
                session.scalars(
                    select(PredictionHypothesisRecord).where(
                        PredictionHypothesisRecord.prediction_snapshot_id
                        == snapshot.prediction_snapshot_id
                    )
                )
            )
            technique = sorted(
                [item for item in rows if item.hypothesis_type == "next_technique"],
                key=lambda item: item.rank,
            )
            assets = sorted(
                [item for item in rows if item.hypothesis_type == "next_asset"],
                key=lambda item: item.rank,
            )
            tactics = sorted(
                [item for item in rows if item.hypothesis_type == "next_tactic"],
                key=lambda item: item.rank,
            )
            objectives = sorted(
                [item for item in rows if item.hypothesis_type == "likely_objective"],
                key=lambda item: item.rank,
            )
            if technique:
                covered += 1
            rank = next(
                (
                    item.rank
                    for item in technique
                    if item.predicted_technique_id == truth["technique"]
                ),
                None,
            )
            reciprocal.append(1 / rank if rank else 0.0)
            top1 += int(rank == 1)
            top3 += int(rank is not None and rank <= 3)
            tactic_hits += int(bool(tactics) and tactics[0].predicted_tactic == truth["tactic"])
            asset_rank = next(
                (item.rank for item in assets if item.predicted_asset_id == truth["asset"]), None
            )
            asset1 += int(asset_rank == 1)
            asset3 += int(asset_rank is not None and asset_rank <= 3)
            objective_hits += int(
                bool(objectives) and objectives[0].predicted_objective == truth["objective"]
            )
            leads.append(int(truth["observed_sequence"]) - sequence)
        count = len(STAGED_DEMO_TRUTH)
        metrics: dict[str, object] = {
            "top_1_technique_accuracy": top1 / count,
            "top_3_technique_accuracy": top3 / count,
            "mean_reciprocal_rank": sum(reciprocal) / count,
            "next_tactic_accuracy": tactic_hits / count,
            "next_asset_top_1_accuracy": asset1 / count,
            "next_asset_top_3_accuracy": asset3 / count,
            "objective_ranking_accuracy": objective_hits / count,
            "prediction_coverage": covered / count,
            "insufficient_evidence_rate": 1 - covered / count,
            "mean_prediction_lead_sequences": sum(leads) / len(leads),
            "predictions_before_observation": sum(lead > 0 for lead in leads),
            "predictions_after_observation": sum(lead <= 0 for lead in leads),
        }
        baseline: dict[str, object] = {
            "name": "most-common-valid-transition",
            "top_1_technique_accuracy": sum(
                item["technique"] == "T1021" for item in STAGED_DEMO_TRUTH.values()
            )
            / count,
            "next_asset_top_1_accuracy": 0.0,
            "limitations": "Tiny synthetic manifest; not production performance.",
        }
        evaluation_id = str(
            uuid5(
                EVAL_NAMESPACE, f"{run_id}:{model_id}:{PREDICTOR_VERSION}:{TRUTH_MANIFEST_VERSION}"
            )
        )
        record = session.get(PredictionEvaluationRecord, evaluation_id)
        if record is None:
            record = PredictionEvaluationRecord(
                evaluation_id=evaluation_id,
                simulation_run_id=run_id,
                model_id=model_id,
                predictor_version=PREDICTOR_VERSION,
                metrics_json=metrics,
                baseline_metrics_json=baseline,
                truth_manifest_version=TRUTH_MANIFEST_VERSION,
                synthetic=True,
                created_at=datetime.now(UTC),
            )
            session.add(record)
            session.flush()
        return self.schema(record)

    @staticmethod
    def schema(record: PredictionEvaluationRecord) -> PredictionEvaluation:
        return PredictionEvaluation(
            evaluation_id=record.evaluation_id,
            simulation_run_id=record.simulation_run_id,
            model_id=record.model_id,
            predictor_version=record.predictor_version,
            metrics=record.metrics_json,
            baseline_metrics=record.baseline_metrics_json,
            truth_manifest_version=record.truth_manifest_version,
            synthetic=True,
            created_at=record.created_at.replace(tzinfo=record.created_at.tzinfo or UTC),
        )


prediction_evaluation_service = PredictionEvaluationService()
