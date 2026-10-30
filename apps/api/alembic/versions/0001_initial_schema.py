"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extensions first: every table below depends on them.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute(
        """
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            firebase_uid TEXT UNIQUE NOT NULL,
            display_name TEXT,
            email TEXT,
            role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user','moderator','admin')),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE spots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            description TEXT,
            category TEXT NOT NULL CHECK (category IN
                ('nature','food','historical','hangout','beach','park','other')),
            state TEXT NOT NULL,
            city TEXT NOT NULL,
            address TEXT,
            location GEOGRAPHY(POINT, 4326) NOT NULL,
            safety_tier TEXT NOT NULL DEFAULT 'unverified'
                CHECK (safety_tier IN ('green','yellow','red','unverified')),
            safety_score NUMERIC(3,1) CHECK (safety_score >= 0 AND safety_score <= 10),
            cost_estimate_text TEXT,
            best_time TEXT,
            amenities JSONB DEFAULT '{}'::jsonb,
            is_verified BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            created_by UUID REFERENCES users(id),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_spots_location ON spots USING GIST (location)")
    op.execute("CREATE INDEX idx_spots_safety_tier ON spots(safety_tier)")
    op.execute("CREATE INDEX idx_spots_state_city ON spots(state, city)")
    op.execute("CREATE INDEX idx_spots_category ON spots(category)")
    op.execute("CREATE INDEX idx_spots_active ON spots(is_active) WHERE is_active = TRUE")

    op.execute(
        """
        CREATE TABLE safety_reports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            spot_id UUID NOT NULL REFERENCES spots(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id),
            reported_tier TEXT NOT NULL CHECK (reported_tier IN ('green','yellow','red')),
            comment TEXT,
            is_moderated BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_safety_reports_spot ON safety_reports(spot_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE spot_photos (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            spot_id UUID NOT NULL REFERENCES spots(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id),
            cloudinary_public_id TEXT NOT NULL,
            is_approved BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_spot_photos_spot ON spot_photos(spot_id) WHERE is_approved = TRUE")

    op.execute(
        """
        CREATE TABLE audit_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            actor_id UUID REFERENCES users(id),
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id UUID,
            metadata JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )


def downgrade() -> None:
    # Reverse dependency order; indexes go with their tables.
    op.execute("DROP TABLE IF EXISTS audit_log")
    op.execute("DROP TABLE IF EXISTS spot_photos")
    op.execute("DROP TABLE IF EXISTS safety_reports")
    op.execute("DROP TABLE IF EXISTS spots")
    op.execute("DROP TABLE IF EXISTS users")
    # Extensions last, in reverse creation order.
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
    op.execute("DROP EXTENSION IF EXISTS postgis")
