"""add provider integrations

Revision ID: ab12cd34ef56
Revises: 6b7c8d9e0f12
Create Date: 2026-06-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ab12cd34ef56"
down_revision: str | Sequence[str] | None = "6b7c8d9e0f12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "provider_integrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("access_token_ciphertext", sa.Text(), nullable=True),
        sa.Column("external_user_id", sa.String(length=255), nullable=True),
        sa.Column("external_username", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_provider_integrations_provider", "provider_integrations", ["provider"])
    op.create_index("idx_provider_integrations_user_id", "provider_integrations", ["user_id"])
    op.create_index(
        "idx_provider_integrations_provider_user_id",
        "provider_integrations",
        ["provider", "user_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_provider_integrations_provider_user_id", table_name="provider_integrations")
    op.drop_index("idx_provider_integrations_user_id", table_name="provider_integrations")
    op.drop_index("idx_provider_integrations_provider", table_name="provider_integrations")
    op.drop_table("provider_integrations")
