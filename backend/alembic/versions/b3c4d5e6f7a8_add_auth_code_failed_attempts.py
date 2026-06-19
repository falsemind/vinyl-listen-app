"""add auth code failed attempts

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-06-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "email_verification_codes",
        sa.Column("failed_attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "email_verification_codes",
        sa.Column("failed_attempt_limited_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "password_reset_codes",
        sa.Column("failed_attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "password_reset_codes",
        sa.Column("failed_attempt_limited_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("password_reset_codes", "failed_attempt_limited_until")
    op.drop_column("password_reset_codes", "failed_attempt_count")
    op.drop_column("email_verification_codes", "failed_attempt_limited_until")
    op.drop_column("email_verification_codes", "failed_attempt_count")
