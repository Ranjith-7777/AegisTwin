"""Operator CLI for recorded datasets.

    python -m app.ingestion import --adapter cicids2017 --file PATH
    python -m app.ingestion import --adapter canonical --file PATH \
        --dataset-name NAME --licence TEXT
    python -m app.ingestion list
    python -m app.ingestion evaluate --train SOURCE_ID --eval SOURCE_ID [--target-fpr 0.01]

Uses the configured DATABASE_URL (run `alembic upgrade head` first). Raw
files are read in place and never copied into the repository.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.database.models import DataSourceRecord
from app.database.session import Database
from app.ingestion.importer import ImportRefused, import_file
from app.services.network_flow.evaluation_service import (
    EvaluationConfig,
    EvaluationRefused,
    evaluate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.ingestion")
    commands = parser.add_subparsers(dest="command", required=True)

    importer = commands.add_parser("import", help="Import one recorded flow file (replay).")
    importer.add_argument("--adapter", required=True, choices=["cicids2017", "canonical"])
    importer.add_argument("--file", required=True, type=Path)
    importer.add_argument("--dataset-name")
    importer.add_argument("--licence")
    importer.add_argument("--imported-by", default="local-operator")

    commands.add_parser("list", help="List imported sources.")

    evaluator = commands.add_parser("evaluate", help="Train on benign, evaluate on labelled.")
    evaluator.add_argument("--train", required=True)
    evaluator.add_argument("--eval", required=True, dest="eval_source")
    evaluator.add_argument("--target-fpr", type=float, default=0.01)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = get_settings()
    if not settings.simulation_only:
        print("Refusing to run: SIMULATION_ONLY must remain true.", file=sys.stderr)
        return 2
    database = Database(settings.database_url)
    session = database.session_factory()
    try:
        if args.command == "import":
            print(f"Importing {args.file} ...", file=sys.stderr)
            result = import_file(
                session,
                args.file,
                args.adapter,
                args.imported_by,
                dataset_name=args.dataset_name,
                licence=args.licence,
            )
            source = result.source
            print(
                json.dumps(
                    {
                        "source_id": source.source_id,
                        "created": result.created,
                        "rows_read": source.rows_read,
                        "rows_accepted": source.rows_accepted,
                        "rows_rejected": source.rows_rejected,
                        "rows_duplicate": source.rows_duplicate,
                        "rows_unmapped": source.rows_unmapped,
                        "rejection_reasons": source.rejection_reasons_json,
                        "labels": source.label_counts_json,
                    },
                    indent=2,
                )
            )
        elif args.command == "list":
            for record in session.scalars(select(DataSourceRecord)):
                print(
                    f"{record.source_id}  {record.source_kind:7}  {record.file_name}  "
                    f"accepted={record.rows_accepted}"
                )
        else:
            print("Training and evaluating ...", file=sys.stderr)
            evaluation = evaluate(
                session,
                args.train,
                args.eval_source,
                settings.model_artifact_dir,
                EvaluationConfig(target_fpr=args.target_fpr),
            )
            print(
                json.dumps(
                    {"evaluation_id": evaluation.evaluation_id, **evaluation.metrics_json},
                    indent=2,
                    default=str,
                )
            )
    except (ImportRefused, EvaluationRefused, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    finally:
        session.close()
        database.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
