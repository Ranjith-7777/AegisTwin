"""Add Blue Agent defense-score columns to synthetic response recommendations."""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260817_0009"
down_revision: Union[str, None] = "20260722_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "response_recommendations",
        sa.Column("defense_score", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "response_recommendations",
        sa.Column("defense_components_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "response_recommendations",
        sa.Column("defense_explanation", sa.String(1000), nullable=False, server_default=""),
    )


def downgrade() -> None:
    for column in ["defense_explanation", "defense_components_json", "defense_score"]:
        op.drop_column("response_recommendations", column)
