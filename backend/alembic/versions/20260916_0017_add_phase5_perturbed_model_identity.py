"""Add Phase 5 perturbed-model-identity column (correcting the partial-
observability robustness test to genuinely restrict the defender's evidence
at decision time, not just at metrics-read time)."""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_0017"
down_revision: Union[str, None] = "20260916_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "experiments",
        sa.Column("perturbed_model_id", sa.String(36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("experiments", "perturbed_model_id")
