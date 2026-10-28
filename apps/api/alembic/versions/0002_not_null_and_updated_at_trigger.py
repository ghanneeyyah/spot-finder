"""NOT NULL flags and timestamps, plus set_updated_at triggers

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-26
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, column, default expression)
COLUMNS: list[tuple[str, str, str]] = [
    ("users", "is_active", "TRUE"),
    ("users", "created_at", "NOW()"),
    ("users", "updated_at", "NOW()"),
    ("spots", "is_active", "TRUE"),
    ("spots", "is_verified", "FALSE"),
    ("spots", "created_at", "NOW()"),
    ("spots", "updated_at", "NOW()"),
    ("safety_reports", "is_moderated", "FALSE"),
    ("safety_reports", "created_at", "NOW()"),
    ("spot_photos", "is_approved", "FALSE"),
    ("spot_photos", "created_at", "NOW()"),
    ("audit_log", "created_at", "NOW()"),
]

TRIGGER_TABLES = ("users", "spots")


def upgrade() -> None:
    for table, column, default in COLUMNS:
        # Backfill first so SET NOT NULL cannot fail on rows written under 0001.
        op.execute(f"UPDATE {table} SET {column} = {default} WHERE {column} IS NULL")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT {default}")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET NOT NULL")

    op.execute(
        """
        CREATE FUNCTION set_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in TRIGGER_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_set_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
            """
        )


def downgrade() -> None:
    for table in TRIGGER_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_set_updated_at ON {table}")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    for table, column, _default in reversed(COLUMNS):
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP NOT NULL")
