"""add session tracks

Revision ID: 2f4a9c1d8e6b
Revises: f7c8d9e0a123
Create Date: 2026-06-07 23:58:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2f4a9c1d8e6b"
down_revision: str | Sequence[str] | None = "f7c8d9e0a123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "session_tracks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("track_position", sa.String(), nullable=False),
        sa.Column("track_title", sa.String(), nullable=False),
        sa.Column("track_duration", sa.String(), nullable=True),
        sa.Column("track_sequence", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_session_tracks_session_id", "session_tracks", ["session_id"], unique=False)
    op.create_index("idx_session_tracks_track_position", "session_tracks", ["track_position"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_session_tracks_track_position", table_name="session_tracks")
    op.drop_index("idx_session_tracks_session_id", table_name="session_tracks")
    op.drop_table("session_tracks")
