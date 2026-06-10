"""add session groups

Revision ID: 8c1d2e3f4a5b
Revises: 2f4a9c1d8e6b
Create Date: 2026-06-10 20:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c1d2e3f4a5b"
down_revision: str | Sequence[str] | None = "2f4a9c1d8e6b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "session_groups",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_session_groups_status", "session_groups", ["status"], unique=False)
    op.create_index("idx_session_groups_started_at", "session_groups", ["started_at"], unique=False)
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("session_group_id", sa.String(), nullable=True))
        batch_op.create_foreign_key(
            "fk_sessions_session_group_id_session_groups",
            "session_groups",
            ["session_group_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("idx_sessions_session_group_id", ["session_group_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_index("idx_sessions_session_group_id")
        batch_op.drop_constraint("fk_sessions_session_group_id_session_groups", type_="foreignkey")
        batch_op.drop_column("session_group_id")
    op.drop_index("idx_session_groups_started_at", table_name="session_groups")
    op.drop_index("idx_session_groups_status", table_name="session_groups")
    op.drop_table("session_groups")
