import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.error_handler import AppError
from app.models import Spot, SpotPhoto, User
from app.schemas.photo import PhotoSubmitted

MIN_IMAGE_BYTES = 12


def sniff_image(data: bytes) -> str | None:
    """Identify JPEG, PNG or WebP by magic bytes. The client's Content-Type is never trusted."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= MIN_IMAGE_BYTES and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


async def spot_is_active(db: AsyncSession, spot_id: uuid.UUID) -> bool:
    found = await db.execute(select(Spot.id).where(Spot.id == spot_id, Spot.is_active.is_(True)))
    return found.scalar_one_or_none() is not None


async def record_photo(
    db: AsyncSession, user: User, spot_id: uuid.UUID, public_id: str
) -> PhotoSubmitted:
    photo = SpotPhoto(spot_id=spot_id, user_id=user.id, cloudinary_public_id=public_id)
    db.add(photo)
    await db.flush()
    await db.commit()
    if not photo.id:
        raise AppError(500, "internal_error", "Something went wrong on our side.")
    return PhotoSubmitted(id=photo.id, spot_id=spot_id)
