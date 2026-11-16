import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.dependencies import (
    AppSettings,
    CurrentUser,
    DbSession,
    Moderator,
    moderation_rate_limit,
    user_rate_limit,
)
from app.middleware.error_handler import AppError
from app.middleware.rate_limit import Rule
from app.schemas.moderation import ModerationDecision, PhotoModerated
from app.schemas.photo import PhotoSubmitted
from app.services import moderation_service, photo_service
from app.services.cloudinary_service import UploadFailed, UploadUnavailable

router = APIRouter(prefix="/api/photos", tags=["photos"])

PHOTO_UPLOAD_LIMIT = Rule(limit=20, window_seconds=3600)


@router.post(
    "",
    status_code=201,
    response_model=PhotoSubmitted,
    dependencies=[Depends(user_rate_limit("photo-upload", PHOTO_UPLOAD_LIMIT))],
)
async def upload_photo(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    settings: AppSettings,
    spot_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
) -> PhotoSubmitted:
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise AppError(413, "payload_too_large", "The image is too large.")
    if photo_service.sniff_image(data) is None:
        raise AppError(415, "unsupported_media_type", "Upload a JPEG, PNG or WebP image.")
    if not await photo_service.spot_is_active(db, spot_id):
        raise AppError(404, "spot_not_found", "Spot not found.")

    try:
        public_id = await request.app.state.uploader.upload(data, folder="spots")
    except UploadUnavailable as exc:
        raise AppError(
            503, "uploads_unavailable", "Photo uploads are temporarily unavailable."
        ) from exc
    except UploadFailed as exc:
        raise AppError(502, "upload_failed", "The photo could not be uploaded. Try again.") from exc
    return await photo_service.record_photo(db, user, spot_id, public_id)


@router.patch(
    "/{photo_id}", response_model=PhotoModerated, dependencies=[Depends(moderation_rate_limit)]
)
async def moderate_photo(
    db: DbSession, moderator: Moderator, photo_id: uuid.UUID, body: ModerationDecision
) -> PhotoModerated:
    """Approve or reject an uploaded photo. Moderators and admins."""
    return await moderation_service.decide_photo(db, moderator, photo_id, body)
