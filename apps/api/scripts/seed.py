"""Seed the database with 8 dummy spots.

Run from apps/api, after `alembic upgrade head`:

    DATABASE_URL=postgresql://... python scripts/seed.py

Every spot is seeded as 'unverified' with no score: tiers come only from real community
reports, so the seed never asserts anything about safety.

Idempotent: a spot whose slug already exists is left untouched, so re-running never
overwrites edits and never deletes real data. Refuses to run when ENVIRONMENT=production.

All spots are owned by one inactive seed user (SEED_FIREBASE_UID). To remove every seed
spot once real data arrives:

    DELETE FROM spots WHERE created_by = (SELECT id FROM users WHERE firebase_uid = 'seed-data');
"""

import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import normalize_database_url
from app.models import Spot, User
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("seed")

SEED_FIREBASE_UID = "seed-data"

# Nigeria's bounding box. Catches swapped lat/lng and typos before they reach the database.
NG_LAT = (4.2, 13.9)
NG_LNG = (2.6, 14.7)


@dataclass(frozen=True)
class SeedSpot:
    name: str
    slug: str
    description: str
    category: str
    state: str
    city: str
    address: str
    lat: float
    lng: float
    safety_tier: str
    safety_score: Decimal | None
    cost_estimate_text: str
    best_time: str
    amenities: dict[str, bool] = field(default_factory=dict)


SPOTS: list[SeedSpot] = [
    SeedSpot(
        name="Lekki Conservation Centre",
        slug="lekki-conservation-centre",
        description="Protected wetland reserve with a long boardwalk and a canopy walkway.",
        category="nature",
        state="Lagos",
        city="Lagos",
        address="Lekki-Epe Expressway, Lekki",
        lat=6.4372,
        lng=3.5350,
        safety_tier="unverified",
        safety_score=None,
        cost_estimate_text="₦3,000 to ₦8,000 per person including the canopy walk",
        best_time="Weekday mornings, November to March",
        amenities={"parking": True, "restrooms": True, "food": True, "guided_tours": True},
    ),
    SeedSpot(
        name="Olumo Rock",
        slug="olumo-rock",
        description="Granite outcrop above Abeokuta with caves, shrines and a summit view.",
        category="historical",
        state="Ogun",
        city="Abeokuta",
        address="Olumo Rock Road, Abeokuta",
        lat=7.1517,
        lng=3.3405,
        safety_tier="unverified",
        safety_score=None,
        cost_estimate_text="₦2,000 to ₦5,000 per person with a guide",
        best_time="Morning, dry season",
        amenities={"parking": True, "restrooms": True, "food": False, "guided_tours": True},
    ),
    SeedSpot(
        name="Elegushi Beach",
        slug="elegushi-beach",
        description="Busy Lagos beach with live music, loungers and street food on weekends.",
        category="beach",
        state="Lagos",
        city="Lagos",
        address="Elegushi, Lekki Phase 1",
        lat=6.4363,
        lng=3.4655,
        safety_tier="unverified",
        safety_score=None,
        cost_estimate_text="₦2,000 to ₦10,000 depending on the day and seating",
        best_time="Weekday afternoons for fewer crowds",
        amenities={"parking": True, "restrooms": True, "food": True, "guided_tours": False},
    ),
    SeedSpot(
        name="Zuma Rock Viewpoint",
        slug="zuma-rock-viewpoint",
        description="Roadside viewpoint of the monolith on the Abuja to Kaduna road.",
        category="nature",
        state="Niger",
        city="Madalla",
        address="Abuja-Kaduna Expressway, Madalla",
        lat=9.1311,
        lng=7.2331,
        safety_tier="unverified",
        safety_score=None,
        cost_estimate_text="Free to view; ₦1,000 to ₦3,000 for parking and local guides",
        best_time="Early morning, dry season",
        amenities={"parking": True, "restrooms": False, "food": False, "guided_tours": False},
    ),
    SeedSpot(
        name="Obudu Mountain Resort",
        slug="obudu-mountain-resort",
        description="Cool-climate plateau resort with a cable car, hiking trails and canopy walk.",
        category="nature",
        state="Cross River",
        city="Obudu",
        address="Obudu Plateau, Cross River",
        lat=6.3667,
        lng=9.3667,
        safety_tier="unverified",
        safety_score=None,
        cost_estimate_text="₦15,000 to ₦60,000 per night; day visits cost less",
        best_time="November to February",
        amenities={"parking": True, "restrooms": True, "food": True, "guided_tours": True},
    ),
    SeedSpot(
        name="Jos Wildlife Park",
        slug="jos-wildlife-park",
        description="Small zoo and picnic park on the Jos Plateau, newly submitted for review.",
        category="park",
        state="Plateau",
        city="Jos",
        address="Rayfield, Jos",
        lat=9.8470,
        lng=8.8680,
        safety_tier="unverified",
        safety_score=None,
        cost_estimate_text="₦1,000 to ₦3,000 per person",
        best_time="Weekday mornings",
        amenities={"parking": True, "restrooms": True, "food": False, "guided_tours": False},
    ),
    SeedSpot(
        name="Okrika Creek Lookout",
        slug="okrika-creek-lookout",
        description="Waterfront hangout with evening grills and boat views over the creek.",
        category="hangout",
        state="Rivers",
        city="Okrika",
        address="Creek Road waterfront, Okrika",
        lat=4.7400,
        lng=7.0800,
        safety_tier="unverified",
        safety_score=None,
        cost_estimate_text="₦3,000 to ₦8,000 for food and drinks",
        best_time="Late afternoon, before dark",
        amenities={"parking": False, "restrooms": False, "food": True, "guided_tours": False},
    ),
    SeedSpot(
        name="Iya Sade Buka",
        slug="iya-sade-buka",
        description="Market-side buka known for amala, ewedu and gbegiri served all day.",
        category="food",
        state="Oyo",
        city="Ibadan",
        address="Bodija Market, Ibadan",
        lat=7.4395,
        lng=3.9168,
        safety_tier="unverified",
        safety_score=None,
        cost_estimate_text="₦1,500 to ₦4,000 per plate",
        best_time="Lunchtime, weekdays",
        amenities={"parking": False, "restrooms": False, "food": True, "guided_tours": False},
    ),
]


def validate(spots: list[SeedSpot]) -> None:
    slugs = [s.slug for s in spots]
    if len(set(slugs)) != len(slugs):
        raise ValueError("duplicate slug in seed data")
    for s in spots:
        if not (NG_LAT[0] <= s.lat <= NG_LAT[1] and NG_LNG[0] <= s.lng <= NG_LNG[1]):
            raise ValueError(f"{s.slug}: ({s.lat}, {s.lng}) is outside Nigeria; lat/lng swapped?")


def spot_row(s: SeedSpot, seed_user_id: Any) -> dict[str, Any]:
    return {
        "name": s.name,
        "slug": s.slug,
        "description": s.description,
        "category": s.category,
        "state": s.state,
        "city": s.city,
        "address": s.address,
        # WKT order is POINT(longitude latitude).
        "location": func.ST_GeogFromText(f"SRID=4326;POINT({s.lng} {s.lat})"),
        "safety_tier": s.safety_tier,
        "safety_score": s.safety_score,
        "cost_estimate_text": s.cost_estimate_text,
        "best_time": s.best_time,
        "amenities": s.amenities,
        "created_by": seed_user_id,
    }


async def seed(database_url: str) -> int:
    engine = create_async_engine(normalize_database_url(database_url))
    try:
        async with engine.begin() as conn:
            await conn.execute(
                insert(User)
                .values(firebase_uid=SEED_FIREBASE_UID, display_name="Seed data", is_active=False)
                .on_conflict_do_nothing(index_elements=["firebase_uid"])
            )
            seed_user_id = (
                await conn.execute(select(User.id).where(User.firebase_uid == SEED_FIREBASE_UID))
            ).scalar_one()
            result = await conn.execute(
                insert(Spot)
                .values([spot_row(s, seed_user_id) for s in SPOTS])
                .on_conflict_do_nothing(index_elements=["slug"])
                .returning(Spot.slug)
            )
            return len(result.scalars().all())
    finally:
        await engine.dispose()


def main() -> None:
    if os.environ.get("ENVIRONMENT", "development").lower() == "production":
        raise SystemExit("Refusing to seed dummy data when ENVIRONMENT=production.")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not set.")
    validate(SPOTS)
    inserted = asyncio.run(seed(database_url))
    log.info("seed complete: %d inserted, %d already present", inserted, len(SPOTS) - inserted)


if __name__ == "__main__":
    main()
