from fastapi import APIRouter, Depends

from app.dependencies import AppSettings, DbSession, require_role
from app.schemas.admin import ModerationItem
from app.schemas.common import Page
from app.services import moderation_service
from app.utils.pagination import Pagination

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_role("moderator"))]
)


@router.get("/moderation-queue", response_model=Page[ModerationItem])
async def get_moderation_queue(
    db: DbSession, settings: AppSettings, page: Pagination
) -> Page[ModerationItem]:
    return await moderation_service.moderation_queue(db, page, settings.cloudinary_cloud_name)
