"""Separate completed-workflow reports from benchmark experiments."""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_0020"
down_revision: Union[str, None] = "20261013_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "experiments",
        sa.Column(
            "evaluation_source",
            sa.String(length=30),
            nullable=False,
            server_default="benchmark",
        ),
    )
    op.create_index(
        "ix_experiments_evaluation_source", "experiments", ["evaluation_source"]
    )


def downgrade() -> None:
    op.drop_index("ix_experiments_evaluation_source", table_name="experiments")
    op.drop_column("experiments", "evaluation_source")
