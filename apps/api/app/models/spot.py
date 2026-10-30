import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Spot(Base):
    __tablename__ = "spots"
    __table_args__ = (
        CheckConstraint(
            "category IN ('nature','food','historical','hangout','beach','park','other')"
        ),
        CheckConstraint("safety_tier IN ('green','yellow','red','unverified')"),
        CheckConstraint("safety_score >= 0 AND safety_score <= 10"),
        Index("idx_spots_location", "location", postgresql_using="gist"),
        Index("idx_spots_safety_tier", "safety_tier"),
        Index("idx_spots_state_city", "state", "city"),
        Index("idx_spots_category", "category"),
        Index("idx_spots_active", "is_active", postgresql_where=text("is_active = TRUE")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    # GEOGRAPHY (not GEOMETRY): ST_DWithin and ST_Distance work in meters.
    # The GIST index is declared explicitly above, so the column's implicit one is off.
    location: Mapped[WKBElement] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    safety_tier: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'unverified'")
    )
    safety_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    cost_estimate_text: Mapped[str | None] = mapped_column(Text)
    best_time: Mapped[str | None] = mapped_column(Text)
    amenities: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Maintained by the set_updated_at() database trigger.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
