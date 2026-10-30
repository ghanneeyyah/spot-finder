"""one safety report per user per spot

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The service checks first for a friendly 409; this index is the backstop that makes two
    # simultaneous submissions from one user impossible. If duplicates already exist this fails
    # loudly instead of silently deleting anyone's report.
    op.execute(
        "CREATE UNIQUE INDEX idx_safety_reports_user_spot ON safety_reports(spot_id, user_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_safety_reports_user_spot")
