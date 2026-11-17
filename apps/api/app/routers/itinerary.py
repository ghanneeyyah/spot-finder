import uuid
from fastapi import APIRouter, Depends, status
from app.dependencies import CurrentUser, DbSession, user_rate_limit
from app.middleware.rate_limit import Rule
from app.schemas.common import Page
from app.schemas.itinerary import SavedSpotOut, SavedSpotUpdate
from app.services import itinerary_service
from app.utils.pagination import Pagination

router = APIRouter(prefix="/api/itinerary", tags=["itinerary"])
ITINERARY_LIMIT = Rule(limit=60, window_seconds=3600)

@router.get("", response_model=Page[SavedSpotOut])
async def get_itinerary(
    db: DbSession, user: CurrentUser, page: Pagination
) -> Page[SavedSpotOut]:
    """Retrieve the user's saved spots and scheduled itinerary."""
    return await itinerary_service.get_itinerary(db, user, page)

@router.post(
    "/{spot_id}",
    status_code=status.HTTP_201_CREATED,
    response_model=SavedSpotOut,
    dependencies=[Depends(user_rate_limit("itinerary-write", ITINERARY_LIMIT))],
)
async def add_to_itinerary(
    db: DbSession, user: CurrentUser, spot_id: uuid.UUID, body: SavedSpotUpdate
) -> SavedSpotOut:
    """Save a spot to the user's itinerary."""
    return await itinerary_service.add_to_itinerary(db, user, spot_id, body)

@router.patch(
    "/{spot_id}",
    response_model=SavedSpotOut,
    dependencies=[Depends(user_rate_limit("itinerary-write", ITINERARY_LIMIT))],
)
async def update_itinerary_entry(
    db: DbSession, user: CurrentUser, spot_id: uuid.UUID, body: SavedSpotUpdate
) -> SavedSpotOut:
    """Update the planned date or notes for a saved spot."""
    return await itinerary_service.update_itinerary_entry(db, user, spot_id, body)

@router.delete(
    "/{spot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(user_rate_limit("itinerary-write", ITINERARY_LIMIT))],
)
async def remove_from_itinerary(
    db: DbSession, user: CurrentUser, spot_id: uuid.UUID
) -> None:
    """Remove a spot from the user's itinerary."""
    await itinerary_service.remove_from_itinerary(db, user, spot_id)