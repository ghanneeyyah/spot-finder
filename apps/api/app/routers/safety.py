import uuid

from fastapi import APIRouter, Depends

from app.dependencies import CurrentUser, DbSession, user_rate_limit
from app.middleware.rate_limit import Rule
from app.schemas.common import Page
from app.schemas.safety import SafetyReportCreate, SafetyReportOut
from app.services import safety_service
from app.utils.pagination import Pagination

router = APIRouter(prefix="/api/safety-reports", tags=["safety"])

SAFETY_REPORT_LIMIT = Rule(limit=20, window_seconds=3600)


@router.post(
    "",
    status_code=201,
    response_model=SafetyReportOut,
    dependencies=[Depends(user_rate_limit("safety-report", SAFETY_REPORT_LIMIT))],
)
async def create_safety_report(
    db: DbSession, user: CurrentUser, body: SafetyReportCreate
) -> SafetyReportOut:
    return await safety_service.create_report(db, user, body)


@router.get("/{spot_id}", response_model=Page[SafetyReportOut])
async def list_safety_reports(
    db: DbSession, page: Pagination, spot_id: uuid.UUID
) -> Page[SafetyReportOut]:
    return await safety_service.list_reports(db, spot_id, page)
