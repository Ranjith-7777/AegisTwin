"""Align PostgreSQL response-impact uniqueness with the ORM.

Revision 0007 created an unnamed ``unique=True`` constraint for
``recommendation_id``. Revision 0018 later added the named unique index the
ORM declares. PostgreSQL retains both objects, so ``alembic check`` reports
the original constraint as schema drift. SQLite represents the original
constraint as an internal auto-index and already passes the drift check, so
only PostgreSQL needs the redundant constraint removed.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261019_0021"
down_revision: str | None = "20261018_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "response_impact_simulations"
CONSTRAINT_NAME = "response_impact_simulations_recommendation_id_key"


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_="unique")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.create_unique_constraint(CONSTRAINT_NAME, TABLE_NAME, ["recommendation_id"])
