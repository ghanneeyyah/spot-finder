from sqlalchemy import Text, func, literal, select, union_all
from sqlalchemy import cast as sql_cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Spot, SpotPhoto
from app.schemas.admin import ModerationItem
from app.schemas.common import Page
from app.services.cloudinary_service import delivery_url
from app.utils.pagination import PageParams


async def moderation_queue(
    db: AsyncSession, page: PageParams, cloud_name: str | None
) -> Page[ModerationItem]:
    """Pending work, oldest first: submitted spots awaiting approval (hidden and unverified) and
    uploaded photos awaiting approval on live spots."""
    pending_spots = select(
        literal("spot", type_=Text).label("kind"),
        Spot.id.label("id"),
        Spot.id.label("spot_id"),
        Spot.name.label("spot_name"),
        sql_cast(None, Text).label("public_id"),
        Spot.created_at.label("created_at"),
    ).where(Spot.is_active.is_(False), Spot.is_verified.is_(False))
    pending_photos = (
        select(
            literal("photo", type_=Text).label("kind"),
            SpotPhoto.id.label("id"),
            SpotPhoto.spot_id.label("spot_id"),
            Spot.name.label("spot_name"),
            SpotPhoto.cloudinary_public_id.label("public_id"),
            SpotPhoto.created_at.label("created_at"),
        )
        .join(Spot, Spot.id == SpotPhoto.spot_id)
        .where(SpotPhoto.is_approved.is_(False), Spot.is_active.is_(True))
    )
    queue = union_all(pending_spots, pending_photos).subquery("queue")

    total = (await db.execute(select(func.count()).select_from(queue))).scalar_one()
    rows = (
        await db.execute(
            select(queue)
            .order_by(queue.c.created_at, queue.c.id)
            .limit(page.limit)
            .offset(page.offset)
        )
    ).all()
    items = [
        ModerationItem(
            kind=row.kind,
            id=row.id,
            spot_id=row.spot_id,
            spot_name=row.spot_name,
            photo_url=(
                delivery_url(cloud_name, row.public_id) if cloud_name and row.public_id else None
            ),
            created_at=row.created_at,
        )
        for row in rows
    ]
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
