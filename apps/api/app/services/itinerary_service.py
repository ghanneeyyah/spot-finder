import uuid
from typing import Any
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.error_handler import AppError
from app.models import SavedSpot, Spot, User
from app.schemas.common import Page
from app.schemas.itinerary import SavedSpotOut, SavedSpotUpdate
from app.schemas.spot import SpotSummary
from app.services.spot_service import _SUMMARY_COLUMNS, _summary_fields
from app.utils.pagination import PageParams


async def add_to_itinerary(
    db: AsyncSession, user: User, spot_id: uuid.UUID, data: SavedSpotUpdate
) -> SavedSpotOut:
    """Save a spot to the user's itinerary. Validates the spot exists and is active."""
    
    spot_query = select(*_SUMMARY_COLUMNS).where(
        Spot.id == spot_id, Spot.is_active.is_(True)
    )
    spot_row = (await db.execute(spot_query)).one_or_none()
    
    if not spot_row:
        raise AppError(404, "spot_not_found", "Spot not found or is currently inactive.")

    saved_spot = SavedSpot(
        user_id=user.id,
        spot_id=spot_id,
        planned_date=data.planned_date,
        notes=data.notes,
    )
    db.add(saved_spot)
    
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError(409, "already_saved", "This spot is already in your itinerary.") from exc

    await db.commit()
    await db.refresh(saved_spot)

    summary = SpotSummary(**_summary_fields(spot_row))
    return SavedSpotOut(
        spot_id=saved_spot.spot_id,
        planned_date=saved_spot.planned_date,
        notes=saved_spot.notes,
        saved_at=saved_spot.saved_at,
        spot=summary,
    )


async def get_itinerary(
    db: AsyncSession, user: User, page: PageParams
) -> Page[SavedSpotOut]:
    """Retrieve the user's saved spots, sorted by planned date (earliest first)."""
    
    total = (
        await db.execute(
            select(func.count()).select_from(SavedSpot).where(SavedSpot.user_id == user.id)
        )
    ).scalar_one()

    query = (
        select(SavedSpot, *_SUMMARY_COLUMNS)
        .join(Spot, Spot.id == SavedSpot.spot_id)
        .where(SavedSpot.user_id == user.id)
        .order_by(SavedSpot.planned_date.asc().nulls_last(), SavedSpot.saved_at.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    rows = (await db.execute(query)).all()

    items = [
        SavedSpotOut(
            spot_id=row.SavedSpot.spot_id,
            planned_date=row.SavedSpot.planned_date,
            notes=row.SavedSpot.notes,
            saved_at=row.SavedSpot.saved_at,
            spot=SpotSummary(**_summary_fields(row)),
        )
        for row in rows
    ]
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


async def update_itinerary_entry(
    db: AsyncSession, user: User, spot_id: uuid.UUID, data: SavedSpotUpdate
) -> SavedSpotOut:
    """Update the date or notes for a specific saved spot."""
    
    query = (
        select(SavedSpot, *_SUMMARY_COLUMNS)
        .join(Spot, Spot.id == SavedSpot.spot_id)
        .where(SavedSpot.user_id == user.id, SavedSpot.spot_id == spot_id)
    )
    row = (await db.execute(query)).one_or_none()

    if not row:
        raise AppError(404, "entry_not_found", "Itinerary entry not found.")

    saved_spot_obj = row.SavedSpot
    saved_spot_obj.planned_date = data.planned_date
    saved_spot_obj.notes = data.notes

    await db.commit()
    await db.refresh(saved_spot_obj)

    return SavedSpotOut(
        spot_id=saved_spot_obj.spot_id,
        planned_date=saved_spot_obj.planned_date,
        notes=saved_spot_obj.notes,
        saved_at=saved_spot_obj.saved_at,
        spot=SpotSummary(**_summary_fields(row)),
    )


async def remove_from_itinerary(
    db: AsyncSession, user: User, spot_id: uuid.UUID
) -> None:
    """Remove a spot from the user's itinerary."""
    
    result = await db.execute(
        delete(SavedSpot).where(SavedSpot.user_id == user.id, SavedSpot.spot_id == spot_id)
    )
    if result.rowcount == 0:
        raise AppError(404, "entry_not_found", "Itinerary entry not found.")
    await db.commit()