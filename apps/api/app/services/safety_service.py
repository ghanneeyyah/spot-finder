import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.error_handler import AppError
from app.models import SafetyReport, Spot, User
from app.schemas.common import Page
from app.schemas.safety import SafetyReportCreate, SafetyReportOut
from app.utils.pagination import PageParams

# Ties resolve toward the more cautious tier.
_CAUTION_ORDER = ("red", "yellow", "green")


def decide_tier(counts: dict[str, int]) -> str:
    """The tier most reporters chose; on a tie, the more cautious one. No reports: unverified."""
    present = {tier: n for tier, n in counts.items() if n > 0}
    if not present:
        return "unverified"
    best = max(present.values())
    return next(tier for tier in _CAUTION_ORDER if present.get(tier) == best)


async def _active_spot_exists(db: AsyncSession, spot_id: uuid.UUID) -> bool:
    found = await db.execute(select(Spot.id).where(Spot.id == spot_id, Spot.is_active.is_(True)))
    return found.scalar_one_or_none() is not None


async def create_report(db: AsyncSession, user: User, data: SafetyReportCreate) -> SafetyReportOut:
    if not await _active_spot_exists(db, data.spot_id):
        raise AppError(404, "spot_not_found", "Spot not found.")
    already = await db.execute(
        select(SafetyReport.id).where(
            SafetyReport.spot_id == data.spot_id, SafetyReport.user_id == user.id
        )
    )
    if already.scalar_one_or_none() is not None:
        raise AppError(409, "already_reported", "You have already reported this spot.")

    report = SafetyReport(
        spot_id=data.spot_id,
        user_id=user.id,
        reported_tier=data.reported_tier,
        comment=data.comment,
    )
    db.add(report)
    await db.flush()

    rows = (
        await db.execute(
            select(SafetyReport.reported_tier, func.count())
            .where(SafetyReport.spot_id == data.spot_id)
            .group_by(SafetyReport.reported_tier)
        )
    ).all()
    tier = decide_tier({tier: count for tier, count in rows})
    await db.execute(update(Spot).where(Spot.id == data.spot_id).values(safety_tier=tier))
    await db.commit()
    await db.refresh(report)
    return SafetyReportOut(
        id=report.id,
        reported_tier=report.reported_tier,
        comment=report.comment,
        created_at=report.created_at,
    )


async def list_reports(
    db: AsyncSession, spot_id: uuid.UUID, page: PageParams
) -> Page[SafetyReportOut]:
    if not await _active_spot_exists(db, spot_id):
        raise AppError(404, "spot_not_found", "Spot not found.")
    total = (
        await db.execute(
            select(func.count()).select_from(SafetyReport).where(SafetyReport.spot_id == spot_id)
        )
    ).scalar_one()
    rows = (
        await db.execute(
            select(SafetyReport)
            .where(SafetyReport.spot_id == spot_id)
            .order_by(SafetyReport.created_at.desc(), SafetyReport.id)
            .limit(page.limit)
            .offset(page.offset)
        )
    ).scalars()
    items = [
        SafetyReportOut(
            id=r.id,
            reported_tier=r.reported_tier,
            comment=r.comment,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
