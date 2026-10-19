"""Widen the response playbook catalogue version column.

The active catalogue identifier is longer than the original VARCHAR(30)
column. SQLite does not enforce that limit, which allowed the mismatch to
escape local tests, while PostgreSQL correctly rejected every workflow that
persisted the playbook catalogue.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261019_0022"
down_revision: str | None = "20261019_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "response_playbook_catalogue"
COLUMN_NAME = "catalogue_version"


def _alter_version_length(existing_length: int, target_length: int) -> None:
    existing_type = sa.String(existing_length)
    target_type = sa.String(target_length)
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(TABLE_NAME) as batch_op:
            batch_op.alter_column(
                COLUMN_NAME,
                existing_type=existing_type,
                type_=target_type,
                existing_nullable=False,
            )
        return
    op.alter_column(
        TABLE_NAME,
        COLUMN_NAME,
        existing_type=existing_type,
        type_=target_type,
        existing_nullable=False,
    )


def upgrade() -> None:
    _alter_version_length(30, 60)


def downgrade() -> None:
    _alter_version_length(60, 30)
