"""saved spots, booking info, and safety report count trigger

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-17

Note on downgrade: Dropping the backfilled safety_report_count is a no-op 
because dropping the column automatically destroys the derived data.
"""
from collections.abc import Sequence
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    # 1. Add booking_info
    op.execute("ALTER TABLE spots ADD COLUMN booking_info JSONB")

    # 2. Add safety_report_count and backfill BEFORE attaching the trigger
    op.execute(
        "ALTER TABLE spots ADD COLUMN safety_report_count INTEGER NOT NULL DEFAULT 0"
    )
    op.execute(
        """
        UPDATE spots s
        SET safety_report_count = (
            SELECT COUNT(*) FROM safety_reports r WHERE r.spot_id = s.id
        )
        """
    )

    # 3. Create the trigger function and trigger for insert/delete with GREATEST guard
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_safety_report_count()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                UPDATE spots
                SET safety_report_count = safety_report_count + 1
                WHERE id = NEW.spot_id;
                RETURN NEW;
            ELSIF TG_OP = 'DELETE' THEN
                UPDATE spots
                SET safety_report_count = GREATEST(safety_report_count - 1, 0)
                WHERE id = OLD.spot_id;
                RETURN OLD;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_safety_report_count
        AFTER INSERT OR DELETE ON safety_reports
        FOR EACH ROW
        EXECUTE FUNCTION update_safety_report_count();
        """
    )

    # 4. Create saved_spots table and optimized indexes
    op.execute(
        """
        CREATE TABLE saved_spots (
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            spot_id UUID NOT NULL REFERENCES spots(id) ON DELETE CASCADE,
            planned_date DATE,
            notes TEXT,
            saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, spot_id)
        )
        """
    )
    op.execute("CREATE INDEX idx_saved_spots_user_id ON saved_spots(user_id)")
    op.execute(
        "CREATE INDEX idx_saved_spots_planned_date ON saved_spots(user_id, planned_date) "
        "WHERE planned_date IS NOT NULL"
    )

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_saved_spots_planned_date")
    op.execute("DROP INDEX IF EXISTS idx_saved_spots_user_id")
    op.execute("DROP TABLE IF EXISTS saved_spots")
    
    op.execute("DROP TRIGGER IF EXISTS trg_safety_report_count ON safety_reports")
    op.execute("DROP FUNCTION IF EXISTS update_safety_report_count()")
    
    op.execute("ALTER TABLE spots DROP COLUMN IF EXISTS safety_report_count")
    op.execute("ALTER TABLE spots DROP COLUMN IF EXISTS booking_info")