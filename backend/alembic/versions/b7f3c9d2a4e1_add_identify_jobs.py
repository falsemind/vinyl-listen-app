"""add identify jobs

Revision ID: b7f3c9d2a4e1
Revises: a5427b530a12
Create Date: 2026-05-12 03:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7f3c9d2a4e1"
down_revision: str | Sequence[str] | None = "a5427b530a12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "identify_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("message", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_identify_jobs_status", "identify_jobs", ["status"])
    op.create_index("idx_identify_jobs_expires_at", "identify_jobs", ["expires_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_identify_jobs_expires_at", table_name="identify_jobs")
    op.drop_index("idx_identify_jobs_status", table_name="identify_jobs")
    op.drop_table("identify_jobs")
