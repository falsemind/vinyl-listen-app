"""scope custom session moods by user

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-06-19 00:00:00.000000

"""

import os
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "e0f1a2b3c4d5"
down_revision: str | Sequence[str] | None = "d9e0f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_OWNER_EMAIL_ENV = "VINYL_LEGACY_OWNER_EMAIL"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("session_moods", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_session_moods_user_id_user_accounts",
        "session_moods",
        "user_accounts",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    if not context.is_offline_mode():
        bind = op.get_bind()
        legacy_owner_id = _resolve_legacy_owner_id(bind)
        if legacy_owner_id is not None:
            bind.execute(
                sa.text("""
                    UPDATE session_moods
                    SET user_id = :owner_id
                    WHERE is_custom IS TRUE AND user_id IS NULL
                    """),
                {"owner_id": legacy_owner_id},
            )

    op.drop_constraint("session_moods_name_key", "session_moods", type_="unique")
    op.create_unique_constraint("uq_session_moods_user_name", "session_moods", ["user_id", "name"])
    op.create_index("idx_session_moods_user_custom", "session_moods", ["user_id", "is_custom"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_session_moods_user_custom", table_name="session_moods")
    op.drop_constraint("uq_session_moods_user_name", "session_moods", type_="unique")
    op.drop_constraint("fk_session_moods_user_id_user_accounts", "session_moods", type_="foreignkey")
    op.drop_column("session_moods", "user_id")
    op.create_unique_constraint("session_moods_name_key", "session_moods", ["name"])


def _resolve_legacy_owner_id(bind: Connection) -> str | None:
    custom_mood_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM session_moods WHERE is_custom IS TRUE AND user_id IS NULL")
    ).scalar_one()
    if int(custom_mood_count) == 0:
        return None

    owner_email = os.getenv(LEGACY_OWNER_EMAIL_ENV)
    if owner_email:
        owner = bind.execute(
            sa.text("""
                SELECT id FROM user_accounts
                WHERE normalized_email = lower(:email)
                  AND is_active IS TRUE
                  AND deleted_at IS NULL
                """),
            {"email": owner_email.strip()},
        ).scalar_one_or_none()
        if owner is None:
            raise RuntimeError(f"{LEGACY_OWNER_EMAIL_ENV} does not match an active account.")
        return str(owner)

    owners = bind.execute(sa.text("""
            SELECT id FROM user_accounts
            WHERE is_active IS TRUE
              AND deleted_at IS NULL
            ORDER BY created_at ASC, id ASC
            """)).scalars().all()
    if len(owners) == 1:
        return str(owners[0])

    raise RuntimeError(
        "Cannot backfill legacy custom session moods without a single active owner. "
        f"Set {LEGACY_OWNER_EMAIL_ENV} to the owner account email and rerun the migration."
    )
