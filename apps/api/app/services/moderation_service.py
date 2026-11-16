import uuid
from typing import Any

from sqlalchemy import Text, func, literal, select, union_all, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.error_handler import AppError
from app.models import AuditLog, Spot, SpotPhoto, User
from app.schemas.admin import ModerationItem, SubmittedSpot
from app.schemas.common import Page
from app.schemas.moderation import ModerationDecision, PhotoModerated, SpotModerated
from app.services.cloudinary_service import delivery_url
from app.services.spot_service import LATITUDE, LONGITUDE
from app.utils.pagination import PageParams


def _record(
    db: AsyncSession,
    actor: User,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    metadata: dict[str, Any],
) -> None:
    """Every moderation action leaves an audit row, written in the same transaction as the change
    itself: either both are saved or neither is."""
    db.add(
        AuditLog(
            actor_id=actor.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_=metadata,
        )
    )


def _spot_state(is_active: bool, is_verified: bool, reason: str | None) -> dict[str, Any]:
    return {"is_active": is_active, "is_verified": is_verified, "rejection_reason": reason}


async def decide_spot(
    db: AsyncSession, actor: User, spot_id: uuid.UUID, decision: ModerationDecision
) -> SpotModerated:
    # FOR UPDATE: two moderators acting on the same spot are serialised, so the second sees the
    # first one's result and gets a clean 409 instead of overwriting it.
    row = (
        await db.execute(
            select(Spot.id, Spot.slug, Spot.is_active, Spot.is_verified, Spot.rejection_reason)
            .where(Spot.id == spot_id)
            .with_for_update()
        )
    ).one_or_none()
    if row is None:
        raise AppError(404, "spot_not_found", "Spot not found.")
    previous = _spot_state(row.is_active, row.is_verified, row.rejection_reason)

    if decision.decision == "approve":
        if row.is_active and row.is_verified:
            raise AppError(409, "already_approved", "This spot is already approved.")
        # Approving a spot that was verified before is putting a removed spot back, not a first
        # approval, and the audit trail says which.
        action = "spot.reactivate" if row.is_verified else "spot.approve"
        new = _spot_state(True, True, None)
        status = "approved"
    else:
        pending = not row.is_active and not row.is_verified and row.rejection_reason is None
        if not pending:
            raise AppError(
                409,
                "not_pending",
                "Only a pending submission can be rejected. Use DELETE to remove a live spot.",
            )
        action = "spot.reject"
        new = _spot_state(False, False, decision.reason)
        status = "rejected"

    await db.execute(update(Spot).where(Spot.id == spot_id).values(**new))
    metadata: dict[str, Any] = {"slug": row.slug, "previous": previous, "new": new}
    if decision.reason:
        metadata["reason"] = decision.reason
    _record(db, actor, action, "spot", spot_id, metadata)
    await db.commit()
    return SpotModerated(id=spot_id, slug=row.slug, status=status)


async def delete_spot(db: AsyncSession, actor: User, spot_id: uuid.UUID) -> SpotModerated:
    """Soft delete only. Nothing is removed: photos, safety reports and the verification flag all
    stay, so approving the spot again restores it exactly as it was."""
    row = (
        await db.execute(
            select(Spot.id, Spot.slug, Spot.is_active, Spot.is_verified, Spot.rejection_reason)
            .where(Spot.id == spot_id)
            .with_for_update()
        )
    ).one_or_none()
    if row is None:
        raise AppError(404, "spot_not_found", "Spot not found.")
    if not row.is_active:
        raise AppError(
            409, "already_inactive", "This spot is not live, so there is nothing to remove."
        )
    previous = _spot_state(row.is_active, row.is_verified, row.rejection_reason)
    new = _spot_state(False, row.is_verified, row.rejection_reason)
    await db.execute(update(Spot).where(Spot.id == spot_id).values(is_active=False))
    _record(
        db,
        actor,
        "spot.delete",
        "spot",
        spot_id,
        {"slug": row.slug, "previous": previous, "new": new},
    )
    await db.commit()
    return SpotModerated(id=spot_id, slug=row.slug, status="deleted")


async def decide_photo(
    db: AsyncSession, actor: User, photo_id: uuid.UUID, decision: ModerationDecision
) -> PhotoModerated:
    row = (
        await db.execute(
            select(
                SpotPhoto.id,
                SpotPhoto.spot_id,
                SpotPhoto.is_approved,
                SpotPhoto.rejection_reason,
            )
            .where(SpotPhoto.id == photo_id)
            .with_for_update()
        )
    ).one_or_none()
    if row is None:
        raise AppError(404, "photo_not_found", "Photo not found.")
    previous: dict[str, Any] = {
        "is_approved": row.is_approved,
        "rejection_reason": row.rejection_reason,
    }

    if decision.decision == "approve":
        if row.is_approved:
            raise AppError(409, "already_approved", "This photo is already approved.")
        action, status = "photo.approve", "approved"
        new: dict[str, Any] = {"is_approved": True, "rejection_reason": None}
    else:
        if row.is_approved or row.rejection_reason is not None:
            raise AppError(409, "not_pending", "Only a pending photo can be rejected.")
        action, status = "photo.reject", "rejected"
        new = {"is_approved": False, "rejection_reason": decision.reason}

    await db.execute(update(SpotPhoto).where(SpotPhoto.id == photo_id).values(**new))
    metadata: dict[str, Any] = {"spot_id": str(row.spot_id), "previous": previous, "new": new}
    if decision.reason:
        metadata["reason"] = decision.reason
    _record(db, actor, action, "photo", photo_id, metadata)
    await db.commit()
    return PhotoModerated(id=photo_id, spot_id=row.spot_id, status=status)


async def moderation_queue(
    db: AsyncSession, page: PageParams, cloud_name: str | None
) -> Page[ModerationItem]:
    """Pending work, oldest first: submitted spots awaiting a decision and uploaded photos awaiting
    a decision on live spots. Rejected items are not pending, so they never reappear."""
    pending_spots = select(
        literal("spot", type_=Text).label("kind"),
        Spot.id.label("id"),
        Spot.created_at.label("created_at"),
    ).where(Spot.is_active.is_(False), Spot.is_verified.is_(False), Spot.rejection_reason.is_(None))
    pending_photos = (
        select(
            literal("photo", type_=Text).label("kind"),
            SpotPhoto.id.label("id"),
            SpotPhoto.created_at.label("created_at"),
        )
        .join(Spot, Spot.id == SpotPhoto.spot_id)
        .where(
            SpotPhoto.is_approved.is_(False),
            SpotPhoto.rejection_reason.is_(None),
            Spot.is_active.is_(True),
        )
    )
    queue = union_all(pending_spots, pending_photos).subquery("queue")

    total = (await db.execute(select(func.count()).select_from(queue))).scalar_one()
    page_rows = (
        await db.execute(
            select(queue)
            .order_by(queue.c.created_at, queue.c.id)
            .limit(page.limit)
            .offset(page.offset)
        )
    ).all()

    # Details for the page are loaded with one query per kind, never one per item.
    spot_ids = [r.id for r in page_rows if r.kind == "spot"]
    photo_ids = [r.id for r in page_rows if r.kind == "photo"]
    spots: dict[uuid.UUID, Any] = {}
    photos: dict[uuid.UUID, Any] = {}
    if spot_ids:
        spot_rows = await db.execute(
            select(
                Spot.id,
                Spot.slug,
                Spot.name,
                Spot.category,
                Spot.state,
                Spot.city,
                Spot.address,
                Spot.description,
                Spot.cost_estimate_text,
                Spot.best_time,
                Spot.amenities,
                LATITUDE,
                LONGITUDE,
                User.display_name,
                User.email,
            )
            .outerjoin(User, User.id == Spot.created_by)
            .where(Spot.id.in_(spot_ids))
        )
        spots = {r.id: r for r in spot_rows}
    if photo_ids:
        photo_rows = await db.execute(
            select(
                SpotPhoto.id,
                SpotPhoto.spot_id,
                SpotPhoto.cloudinary_public_id,
                Spot.name,
                Spot.slug,
                User.display_name,
                User.email,
            )
            .join(Spot, Spot.id == SpotPhoto.spot_id)
            .outerjoin(User, User.id == SpotPhoto.user_id)
            .where(SpotPhoto.id.in_(photo_ids))
        )
        photos = {r.id: r for r in photo_rows}

    items: list[ModerationItem] = []
    for entry in page_rows:
        if entry.kind == "spot":
            s = spots[entry.id]
            items.append(
                ModerationItem(
                    kind="spot",
                    id=s.id,
                    spot_id=s.id,
                    spot_name=s.name,
                    spot_slug=s.slug,
                    submitter=s.display_name or s.email,
                    photo_url=None,
                    spot=SubmittedSpot(
                        category=s.category,
                        state=s.state,
                        city=s.city,
                        address=s.address,
                        description=s.description,
                        cost_estimate_text=s.cost_estimate_text,
                        best_time=s.best_time,
                        amenities=s.amenities or {},
                        latitude=s.latitude,
                        longitude=s.longitude,
                    ),
                    created_at=entry.created_at,
                )
            )
        else:
            p = photos[entry.id]
            items.append(
                ModerationItem(
                    kind="photo",
                    id=p.id,
                    spot_id=p.spot_id,
                    spot_name=p.name,
                    spot_slug=p.slug,
                    submitter=p.display_name or p.email,
                    photo_url=delivery_url(cloud_name, p.cloudinary_public_id)
                    if cloud_name
                    else None,
                    spot=None,
                    created_at=entry.created_at,
                )
            )
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
