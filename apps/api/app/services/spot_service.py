import secrets
from dataclasses import dataclass
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Row, and_, func, or_, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.error_handler import AppError
from app.models import SafetyReport, Spot, SpotPhoto, User
from app.schemas.common import Page
from app.schemas.spot import (
    PhotoOut,
    SpotCreate,
    SpotDetail,
    SpotNearby,
    SpotSubmitted,
    SpotSummary,
)
from app.services.cloudinary_service import delivery_url
from app.utils.geo import BBox, geog_bbox, geog_point
from app.utils.pagination import PageParams
from app.utils.slug import slugify

_LAT = func.ST_Y(sql_cast(Spot.location, Geometry)).label("latitude")
_LNG = func.ST_X(sql_cast(Spot.location, Geometry)).label("longitude")
# One correlated subquery per row, so listing never issues a query per spot (no N+1).
_REPORT_COUNT = (
    select(func.count(SafetyReport.id))
    .where(SafetyReport.spot_id == Spot.id)
    .correlate(Spot)
    .scalar_subquery()
    .label("safety_report_count")
)
_SUMMARY_COLUMNS = (
    Spot.id,
    Spot.slug,
    Spot.name,
    Spot.category,
    Spot.state,
    Spot.city,
    Spot.safety_tier,
    _LAT,
    _LNG,
    _REPORT_COUNT,
)
MAX_PHOTOS_ON_DETAIL = 10


@dataclass(frozen=True)
class SpotFilters:
    state: str | None = None
    city: str | None = None
    category: str | None = None
    safety_tier: str | None = None
    q: str | None = None
    bbox: BBox | None = None


def display_tier(stored_tier: str, report_count: int) -> str:
    """A tier is only shown once community reports exist to back it."""
    return stored_tier if report_count > 0 else "unverified"


def _like_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _conditions(filters: SpotFilters) -> list[Any]:
    conditions: list[Any] = [Spot.is_active.is_(True)]
    if filters.state:
        conditions.append(Spot.state == filters.state)
    if filters.city:
        conditions.append(Spot.city == filters.city)
    if filters.category:
        conditions.append(Spot.category == filters.category)
    if filters.safety_tier:
        conditions.append(Spot.safety_tier == filters.safety_tier)
    if filters.q:
        pattern = _like_pattern(filters.q)
        conditions.append(
            or_(Spot.name.ilike(pattern, escape="\\"), Spot.city.ilike(pattern, escape="\\"))
        )
    if filters.bbox:
        conditions.append(func.ST_Intersects(Spot.location, geog_bbox(filters.bbox)))
    return conditions


def _summary_fields(row: Row[Any]) -> dict[str, Any]:
    return {
        "id": row.id,
        "slug": row.slug,
        "name": row.name,
        "category": row.category,
        "state": row.state,
        "city": row.city,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "display_tier": display_tier(row.safety_tier, row.safety_report_count),
        "safety_report_count": row.safety_report_count,
    }


async def list_spots(db: AsyncSession, filters: SpotFilters, page: PageParams) -> Page[SpotSummary]:
    conditions = _conditions(filters)
    total = (
        await db.execute(select(func.count()).select_from(Spot).where(*conditions))
    ).scalar_one()
    rows = (
        await db.execute(
            select(*_SUMMARY_COLUMNS)
            .where(*conditions)
            .order_by(Spot.name, Spot.id)
            .limit(page.limit)
            .offset(page.offset)
        )
    ).all()
    items = [SpotSummary(**_summary_fields(row)) for row in rows]
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


async def nearby_spots(
    db: AsyncSession, lat: float, lng: float, radius_km: float, page: PageParams
) -> Page[SpotNearby]:
    origin = geog_point(lng, lat)
    within = and_(
        Spot.is_active.is_(True), func.ST_DWithin(Spot.location, origin, radius_km * 1000)
    )
    distance = func.ST_Distance(Spot.location, origin).label("distance_m")
    total = (await db.execute(select(func.count()).select_from(Spot).where(within))).scalar_one()
    rows = (
        await db.execute(
            select(*_SUMMARY_COLUMNS, distance)
            .where(within)
            .order_by(distance, Spot.id)
            .limit(page.limit)
            .offset(page.offset)
        )
    ).all()
    items = [
        SpotNearby(**_summary_fields(row), distance_m=round(float(row.distance_m), 1))
        for row in rows
    ]
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


async def get_spot_detail(db: AsyncSession, slug: str, cloud_name: str | None) -> SpotDetail | None:
    row = (
        await db.execute(
            select(
                *_SUMMARY_COLUMNS,
                Spot.safety_score,
                Spot.description,
                Spot.address,
                Spot.cost_estimate_text,
                Spot.best_time,
                Spot.amenities,
                Spot.is_verified,
                Spot.created_at,
                Spot.updated_at,
            ).where(Spot.slug == slug, Spot.is_active.is_(True))
        )
    ).one_or_none()
    if row is None:
        return None

    photos: list[PhotoOut] = []
    if cloud_name:
        photo_rows = (
            await db.execute(
                select(SpotPhoto.id, SpotPhoto.cloudinary_public_id)
                .where(SpotPhoto.spot_id == row.id, SpotPhoto.is_approved.is_(True))
                .order_by(SpotPhoto.created_at, SpotPhoto.id)
                .limit(MAX_PHOTOS_ON_DETAIL)
            )
        ).all()
        photos = [
            PhotoOut(id=p.id, url=delivery_url(cloud_name, p.cloudinary_public_id))
            for p in photo_rows
        ]

    fields = _summary_fields(row)
    has_reports = row.safety_report_count > 0
    return SpotDetail(
        **fields,
        safety_tier=row.safety_tier,
        # A score with no reports behind it would be an unsupported claim, so it stays hidden.
        safety_score=float(row.safety_score)
        if has_reports and row.safety_score is not None
        else None,
        description=row.description,
        address=row.address,
        cost_estimate_text=row.cost_estimate_text,
        best_time=row.best_time,
        amenities=row.amenities or {},
        is_verified=row.is_verified,
        photos=photos,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def create_spot(db: AsyncSession, user: User, data: SpotCreate) -> SpotSubmitted:
    """Creates a spot that stays hidden (inactive and unverified) until a moderator approves it."""
    base = slugify(data.name)
    candidates = [base, *(f"{base}-{n}" for n in range(2, 6)), f"{base}-{secrets.token_hex(3)}"]
    for slug in candidates:
        spot = Spot(
            name=data.name,
            slug=slug,
            description=data.description,
            category=data.category,
            state=data.state,
            city=data.city,
            address=data.address,
            location=geog_point(data.longitude, data.latitude),
            cost_estimate_text=data.cost_estimate_text,
            best_time=data.best_time,
            amenities=data.amenities,
            is_active=False,
            is_verified=False,
            created_by=user.id,
        )
        try:
            async with db.begin_nested():
                db.add(spot)
                await db.flush()
        except IntegrityError as exc:
            if "spots_slug_key" in str(exc):
                continue
            raise
        await db.commit()
        return SpotSubmitted(id=spot.id, slug=slug, name=data.name)
    raise AppError(409, "slug_conflict", "Could not allocate a unique address for this spot.")
