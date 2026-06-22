"""add manual release session target

Revision ID: a8b9c0d1e2f3
Revises: e7f8a9b0c1d2
Create Date: 2026-06-22 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8b9c0d1e2f3"
down_revision: str | Sequence[str] | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("manual_release_id", sa.String(length=36), nullable=True))
        batch_op.alter_column("release_id", existing_type=sa.String(), nullable=True)
        batch_op.create_foreign_key(
            "fk_sessions_manual_release_id_manual_releases",
            "manual_releases",
            ["manual_release_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_check_constraint(
            "ck_sessions_exactly_one_release_target",
            "(release_id IS NOT NULL AND manual_release_id IS NULL) "
            "OR (release_id IS NULL AND manual_release_id IS NOT NULL)",
        )
        batch_op.create_index("idx_sessions_user_manual_release_id", ["user_id", "manual_release_id"])
        batch_op.create_index("idx_sessions_manual_release_id", ["manual_release_id"])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_index("idx_sessions_manual_release_id")
        batch_op.drop_index("idx_sessions_user_manual_release_id")
        batch_op.drop_constraint("ck_sessions_exactly_one_release_target", type_="check")
        batch_op.drop_constraint("fk_sessions_manual_release_id_manual_releases", type_="foreignkey")
        batch_op.alter_column("release_id", existing_type=sa.String(), nullable=False)
        batch_op.drop_column("manual_release_id")
