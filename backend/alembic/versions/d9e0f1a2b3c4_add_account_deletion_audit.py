"""add account deletion audit

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-06-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9e0f1a2b3c4"
down_revision: str | Sequence[str] | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "account_deletion_audits",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_account_deletion_audits_deleted_at",
        "account_deletion_audits",
        ["deleted_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_account_deletion_audits_deleted_at", table_name="account_deletion_audits")
    op.drop_table("account_deletion_audits")
