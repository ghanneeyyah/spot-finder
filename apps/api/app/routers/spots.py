from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.dependencies import AppSettings, CurrentUser, DbSession, user_rate_limit
from app.middleware.error_handler import AppError
from app.middleware.rate_limit import Rule
from app.schemas.common import Page
from app.schemas.spot import (
    Category,
    SpotCreate,
    SpotDetail,
    SpotNearby,
    SpotSubmitted,
    SpotSummary,
    Tier,
)
from app.services import spot_service
from app.services.spot_service import SpotFilters
from app.utils.geo import NG_LAT, NG_LNG, parse_bbox
from app.utils.pagination import Pagination

router = APIRouter(prefix="/api/spots", tags=["spots"])

SPOT_SUBMISSION_LIMIT = Rule(limit=10, window_seconds=3600)
ShortText = Annotated[str | None, Query(min_length=1, max_length=80)]


@router.get("", response_model=Page[SpotSummary])
async def list_spots(
    db: DbSession,
    page: Pagination,
    state: ShortText = None,
    city: ShortText = None,
    category: Category | None = None,
    safety_tier: Tier | None = None,
    q: Annotated[
        str | None, Query(min_length=1, max_length=80, description="Name or city.")
    ] = None,
    bbox: Annotated[
        str | None, Query(max_length=120, description="min_lng,min_lat,max_lng,max_lat")
    ] = None,
) -> Page[SpotSummary]:
    box = None
    if bbox is not None:
        try:
            box = parse_bbox(bbox)
        except ValueError as exc:
            raise AppError(
                422,
                "validation_error",
                "The request is invalid.",
                [{"field": "query.bbox", "message": str(exc), "type": "value_error"}],
            ) from exc
    filters = SpotFilters(
        state=state, city=city, category=category, safety_tier=safety_tier, q=q, bbox=box
    )
    return await spot_service.list_spots(db, filters, page)


# Declared before /{slug} so "nearby" is never read as a slug.
@router.get("/nearby", response_model=Page[SpotNearby])
async def nearby_spots(
    db: DbSession,
    page: Pagination,
    lat: Annotated[float, Query(ge=NG_LAT[0], le=NG_LAT[1])],
    lng: Annotated[float, Query(ge=NG_LNG[0], le=NG_LNG[1])],
    radius_km: Annotated[float, Query(gt=0, le=100)] = 10,
) -> Page[SpotNearby]:
    return await spot_service.nearby_spots(db, lat, lng, radius_km, page)


@router.get("/{slug}", response_model=SpotDetail)
async def get_spot(
    db: DbSession,
    settings: AppSettings,
    slug: Annotated[str, Path(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)],
) -> SpotDetail:
    spot = await spot_service.get_spot_detail(db, slug, settings.cloudinary_cloud_name)
    if spot is None:
        raise AppError(404, "spot_not_found", "Spot not found.")
    return spot


@router.post(
    "",
    status_code=201,
    response_model=SpotSubmitted,
    dependencies=[Depends(user_rate_limit("spot-submission", SPOT_SUBMISSION_LIMIT))],
)
async def submit_spot(db: DbSession, user: CurrentUser, body: SpotCreate) -> SpotSubmitted:
    return await spot_service.create_spot(db, user, body)
