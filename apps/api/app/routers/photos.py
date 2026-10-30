import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.dependencies import AppSettings, CurrentUser, DbSession, user_rate_limit
from app.middleware.error_handler import AppError
from app.middleware.rate_limit import Rule
from app.schemas.photo import PhotoSubmitted
from app.services import photo_service
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
