"""moderation: rejection reasons and pending-queue indexes

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A rejected item stays in the table (so a submitter can be told why) but must not appear in
    # the pending queue, so rejection needs its own marker. The reason is that marker.
    op.execute(
        "ALTER TABLE spots ADD COLUMN rejection_reason TEXT "
        "CHECK (char_length(rejection_reason) <= 500)"
    )
    op.execute(
        "ALTER TABLE spot_photos ADD COLUMN rejection_reason TEXT "
        "CHECK (char_length(rejection_reason) <= 500)"
    )
    # The moderation queue reads only pending rows, oldest first.
    op.execute(
        "CREATE INDEX idx_spots_pending ON spots(created_at, id) "
        "WHERE is_active = FALSE AND is_verified = FALSE AND rejection_reason IS NULL"
    )
    op.execute(
        "CREATE INDEX idx_spot_photos_pending ON spot_photos(created_at, id) "
        "WHERE is_approved = FALSE AND rejection_reason IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_spot_photos_pending")
    op.execute("DROP INDEX IF EXISTS idx_spots_pending")
    op.execute("ALTER TABLE spot_photos DROP COLUMN IF EXISTS rejection_reason")
    op.execute("ALTER TABLE spots DROP COLUMN IF EXISTS rejection_reason")
