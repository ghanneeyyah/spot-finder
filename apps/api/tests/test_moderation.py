import asyncio
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from app.config import Settings
from app.main import create_app
from app.models import AuditLog, SafetyReport, Spot, SpotPhoto, User
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import FakeVerifier, add_spot, auth, make_settings

PENDING = {
    "name": "Ikogosi Warm Springs",
    "category": "nature",
    "state": "Ekiti",
    "city": "Ikogosi",
    "latitude": 7.5833,
    "longitude": 4.9833,
}
APPROVE = {"decision": "approve"}


def reject(reason: str = "Duplicate of an existing spot") -> dict[str, str]:
    return {"decision": "reject", "reason": reason}


async def submit(client: httpx.AsyncClient, token: str = "tok-alice") -> dict[str, Any]:
    response = await client.post("/api/spots", json=PENDING, headers=auth(token))
    assert response.status_code == 201
    return dict(response.json())


async def patch_spot(
    client: httpx.AsyncClient, spot_id: object, body: dict[str, Any], token: str = "tok-mod"
) -> httpx.Response:
    return await client.patch(f"/api/spots/{spot_id}", json=body, headers=auth(token))


async def audit_rows(db: AsyncSession, entity_id: object) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.entity_id == entity_id)
        .order_by(AuditLog.created_at, AuditLog.id)
    )
    return list(result.scalars())


def meta(row: AuditLog) -> dict[str, Any]:
    assert row.metadata_ is not None
    return row.metadata_


async def load_spot(db: AsyncSession, spot_id: object) -> Spot:
    db.expire_all()
    return (await db.execute(select(Spot).where(Spot.id == spot_id))).scalar_one()


async def user_id(db: AsyncSession, uid: str) -> uuid.UUID:
    return (await db.execute(select(User.id).where(User.firebase_uid == uid))).scalar_one()


pytestmark = pytest.mark.usefixtures("staff")


# --- PATCH: approve -----------------------------------------------------------------------------


async def test_moderator_approval_makes_the_spot_public(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    created = await submit(client)
    assert (await client.get("/api/spots")).json()["total"] == 0

    response = await patch_spot(client, created["id"], APPROVE)
    assert response.status_code == 200
    assert response.json() == {"id": created["id"], "slug": created["slug"], "status": "approved"}

    assert (await client.get("/api/spots")).json()["total"] == 1
    assert (await client.get(f"/api/spots/{created['slug']}")).status_code == 200
    queue = await client.get("/api/admin/moderation-queue", headers=auth("tok-mod"))
    assert queue.json()["total"] == 0

    spot = await load_spot(db, created["id"])
    assert (spot.is_active, spot.is_verified, spot.rejection_reason) == (True, True, None)
    # The set_updated_at trigger moved the timestamp without the application touching it.
    assert spot.updated_at > spot.created_at


async def test_every_decision_is_written_to_the_audit_log(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    created = await submit(client)
    await patch_spot(
        client, created["id"], {"decision": "approve", "reason": "Verified with the owner"}
    )
    (row,) = await audit_rows(db, uuid.UUID(created["id"]))
    assert row.action == "spot.approve" and row.entity_type == "spot"
    assert row.actor_id == await user_id(db, "mod")
    assert meta(row) == {
        "slug": created["slug"],
        "previous": {"is_active": False, "is_verified": False, "rejection_reason": None},
        "new": {"is_active": True, "is_verified": True, "rejection_reason": None},
        "reason": "Verified with the owner",
    }


async def test_admins_can_moderate_too(client: httpx.AsyncClient) -> None:
    created = await submit(client)
    assert (await patch_spot(client, created["id"], APPROVE, "tok-admin")).status_code == 200


async def test_a_moderator_may_act_on_their_own_submission(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    created = await submit(client, "tok-mod")
    assert (await patch_spot(client, created["id"], APPROVE, "tok-mod")).status_code == 200
    assert (await load_spot(db, created["id"])).is_active is True


# --- PATCH: reject ------------------------------------------------------------------------------


async def test_rejection_hides_the_spot_and_records_why(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    created = await submit(client)
    response = await patch_spot(client, created["id"], reject("Not a real location"))
    assert response.status_code == 200 and response.json()["status"] == "rejected"

    spot = await load_spot(db, created["id"])
    assert (spot.is_active, spot.is_verified, spot.rejection_reason) == (
        False,
        False,
        "Not a real location",
    )
    assert (await client.get("/api/spots")).json()["total"] == 0
    assert (await client.get(f"/api/spots/{created['slug']}")).status_code == 404
    queue = await client.get("/api/admin/moderation-queue", headers=auth("tok-mod"))
    assert queue.json()["total"] == 0  # rejected is not pending, so it never reappears

    (row,) = await audit_rows(db, uuid.UUID(created["id"]))
    assert row.action == "spot.reject" and meta(row)["reason"] == "Not a real location"
    assert meta(row)["new"]["rejection_reason"] == "Not a real location"


@pytest.mark.parametrize(
    "body",
    [
        {"decision": "reject"},
        {"decision": "reject", "reason": ""},
        {"decision": "reject", "reason": "   \n "},
        {"decision": "reject", "reason": "x" * 501},
        {"decision": "maybe"},
        {"decision": "approve", "is_active": True},
        {},
    ],
)
async def test_invalid_decisions_are_rejected_before_anything_changes(
    client: httpx.AsyncClient, db: AsyncSession, body: dict[str, Any]
) -> None:
    created = await submit(client)
    response = await patch_spot(client, created["id"], body)
    assert response.status_code == 422 and response.json()["error"]["code"] == "validation_error"
    assert await audit_rows(db, uuid.UUID(created["id"])) == []
    assert (await load_spot(db, created["id"])).rejection_reason is None


async def test_state_conflicts_return_409_and_write_no_audit_row(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    live_id = (await add_spot(db, "Live Spot", is_verified=False)).id
    pending = await submit(client)
    await patch_spot(client, pending["id"], reject())

    rejecting_live = await patch_spot(client, live_id, reject())
    assert rejecting_live.status_code == 409
    assert rejecting_live.json()["error"]["code"] == "not_pending"
    rejecting_twice = await patch_spot(client, pending["id"], reject("again"))
    assert rejecting_twice.status_code == 409

    await patch_spot(client, live_id, APPROVE)  # verifies a live, unverified spot
    approving_twice = await patch_spot(client, live_id, APPROVE)
    assert approving_twice.status_code == 409
    assert approving_twice.json()["error"]["code"] == "already_approved"
    assert len(await audit_rows(db, live_id)) == 1


async def test_a_rejected_spot_can_be_reconsidered(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    created = await submit(client)
    await patch_spot(client, created["id"], reject("Wrong location"))
    assert (await patch_spot(client, created["id"], APPROVE)).status_code == 200
    spot = await load_spot(db, created["id"])
    assert (spot.is_active, spot.rejection_reason) == (True, None)
    approve_row = (await audit_rows(db, uuid.UUID(created["id"])))[-1]
    assert meta(approve_row)["previous"]["rejection_reason"] == "Wrong location"


async def test_unknown_and_malformed_ids(client: httpx.AsyncClient) -> None:
    missing = await patch_spot(client, uuid.uuid4(), APPROVE)
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "spot_not_found"
    assert (await patch_spot(client, "not-a-uuid", APPROVE)).status_code == 422
    gone = await client.delete(f"/api/spots/{uuid.uuid4()}", headers=auth("tok-admin"))
    assert gone.status_code == 404


# --- access control -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path_template,body",
    [
        ("PATCH", "/api/spots/{id}", APPROVE),
        ("DELETE", "/api/spots/{id}", None),
        ("PATCH", "/api/photos/{id}", APPROVE),
    ],
)
async def test_unauthenticated_requests_get_401(
    client: httpx.AsyncClient, method: str, path_template: str, body: dict[str, Any] | None
) -> None:
    path = path_template.format(id=uuid.uuid4())
    for headers in ({}, auth("not-a-real-token")):
        response = await client.request(method, path, json=body, headers=headers)
        assert response.status_code == 401, headers
        assert response.json()["error"]["code"] in {"not_authenticated", "invalid_token"}


async def test_regular_users_get_403_everywhere(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    spot = await add_spot(db, "Live Spot")
    spot_id = spot.id
    photo = SpotPhoto(spot_id=spot_id, cloudinary_public_id="spots/p")
    db.add(photo)
    await db.commit()
    photo_id = photo.id
    for response in (
        await patch_spot(client, spot_id, APPROVE, "tok-alice"),
        await client.delete(f"/api/spots/{spot_id}", headers=auth("tok-alice")),
        await client.patch(f"/api/photos/{photo_id}", json=APPROVE, headers=auth("tok-alice")),
        await patch_spot(client, spot_id, APPROVE, "tok-disabled"),
    ):
        assert response.status_code == 403
    assert (await load_spot(db, spot_id)).is_active is True
    assert await audit_rows(db, spot_id) == []


async def test_only_admins_may_delete(client: httpx.AsyncClient, db: AsyncSession) -> None:
    spot_id = (await add_spot(db, "Live Spot")).id
    forbidden = await client.delete(f"/api/spots/{spot_id}", headers=auth("tok-mod"))
    assert forbidden.status_code == 403 and forbidden.json()["error"]["code"] == "forbidden"
    assert (await load_spot(db, spot_id)).is_active is True


# --- DELETE (soft) ------------------------------------------------------------------------------


async def test_admin_delete_hides_the_spot_but_erases_nothing(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    spot_id = (await add_spot(db, "Doomed Spot", is_verified=True)).id
    reporter = User(firebase_uid="reporter")
    db.add(reporter)
    await db.flush()
    db.add(SafetyReport(spot_id=spot_id, user_id=reporter.id, reported_tier="green"))
    db.add(SpotPhoto(spot_id=spot_id, cloudinary_public_id="spots/keep", is_approved=True))
    await db.commit()

    response = await client.delete(f"/api/spots/{spot_id}", headers=auth("tok-admin"))
    assert response.status_code == 200 and response.json()["status"] == "deleted"

    assert (await client.get("/api/spots")).json()["total"] == 0
    assert (await client.get("/api/spots/doomed-spot")).status_code == 404
    assert (await client.get(f"/api/safety-reports/{spot_id}")).status_code == 404

    stored = await load_spot(db, spot_id)
    assert (stored.is_active, stored.is_verified) == (False, True)  # verification is kept
    reports = (await db.execute(select(func.count()).select_from(SafetyReport))).scalar_one()
    photos = (await db.execute(select(func.count()).select_from(SpotPhoto))).scalar_one()
    assert (reports, photos) == (1, 1)

    (row,) = await audit_rows(db, spot_id)
    assert row.action == "spot.delete" and row.actor_id == await user_id(db, "admin")
    assert meta(row)["previous"] == {
        "is_active": True,
        "is_verified": True,
        "rejection_reason": None,
    }
    assert meta(row)["new"]["is_active"] is False


async def test_a_deleted_spot_can_be_reactivated_with_everything_intact(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    spot_id = (await add_spot(db, "Comeback Spot", is_verified=True)).id
    reporter = User(firebase_uid="reporter")
    db.add(reporter)
    await db.flush()
    db.add(SafetyReport(spot_id=spot_id, user_id=reporter.id, reported_tier="green"))
    await db.commit()

    await client.delete(f"/api/spots/{spot_id}", headers=auth("tok-admin"))
    again = await client.delete(f"/api/spots/{spot_id}", headers=auth("tok-admin"))
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_inactive"

    assert (await patch_spot(client, spot_id, APPROVE)).status_code == 200
    detail = (await client.get("/api/spots/comeback-spot")).json()
    assert detail["safety_report_count"] == 1  # the report survived the removal
    actions = [row.action for row in await audit_rows(db, spot_id)]
    assert actions == ["spot.delete", "spot.reactivate"]


async def test_deleting_a_pending_submission_is_refused(client: httpx.AsyncClient) -> None:
    created = await submit(client)
    response = await client.delete(f"/api/spots/{created['id']}", headers=auth("tok-admin"))
    assert response.status_code == 409  # reject it instead, so the submitter gets a reason


# --- concurrency --------------------------------------------------------------------------------


async def test_simultaneous_decisions_cannot_both_win(
    make_client: Callable[..., httpx.AsyncClient], client: httpx.AsyncClient, db: AsyncSession
) -> None:
    created = await submit(client)

    async def approve() -> int:
        async with make_client() as c:
            return (await patch_spot(c, created["id"], APPROVE)).status_code

    codes = sorted(await asyncio.gather(*(approve() for _ in range(6))))
    assert codes.count(200) == 1 and codes.count(409) == 5
    assert len(await audit_rows(db, uuid.UUID(created["id"]))) == 1


# --- photos -------------------------------------------------------------------------------------


async def test_photo_approval_and_rejection(client: httpx.AsyncClient, db: AsyncSession) -> None:
    spot = await add_spot(db, "Photo Spot")
    good = SpotPhoto(spot_id=spot.id, cloudinary_public_id="spots/good")
    bad = SpotPhoto(spot_id=spot.id, cloudinary_public_id="spots/bad")
    db.add_all([good, bad])
    await db.commit()
    good_id, bad_id = good.id, bad.id

    approved = await client.patch(f"/api/photos/{good_id}", json=APPROVE, headers=auth("tok-mod"))
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    rejected = await client.patch(
        f"/api/photos/{bad_id}", json=reject("Not this place"), headers=auth("tok-mod")
    )
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"

    urls = [p["url"] for p in (await client.get("/api/spots/photo-spot")).json()["photos"]]
    assert urls == ["https://res.cloudinary.com/democloud/image/upload/f_auto,q_auto/spots/good"]
    queue = await client.get("/api/admin/moderation-queue", headers=auth("tok-mod"))
    assert queue.json()["total"] == 0

    db.expire_all()
    stored = (await db.execute(select(SpotPhoto).where(SpotPhoto.id == bad_id))).scalar_one()
    assert (stored.is_approved, stored.rejection_reason) == (False, "Not this place")
    assert [r.action for r in await audit_rows(db, good_id)] == ["photo.approve"]
    (bad_row,) = await audit_rows(db, bad_id)
    assert bad_row.action == "photo.reject" and meta(bad_row)["reason"] == "Not this place"

    again = await client.patch(f"/api/photos/{good_id}", json=reject(), headers=auth("tok-mod"))
    assert again.status_code == 409
    missing = await client.patch(
        f"/api/photos/{uuid.uuid4()}", json=APPROVE, headers=auth("tok-mod")
    )
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "photo_not_found"


# --- queue content, CORS, rate limiting ---------------------------------------------------------


async def test_queue_items_carry_what_a_moderator_needs(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    created = await submit(client)  # alice, display name "Alice"
    live = await add_spot(db, "Live Spot")
    live_id = live.id
    alice = await user_id(db, "alice")
    db.add(SpotPhoto(spot_id=live_id, user_id=alice, cloudinary_public_id="spots/waiting"))
    await db.commit()

    body = (await client.get("/api/admin/moderation-queue", headers=auth("tok-mod"))).json()
    spot_item = next(i for i in body["items"] if i["kind"] == "spot")
    photo_item = next(i for i in body["items"] if i["kind"] == "photo")
    assert spot_item["id"] == created["id"] and spot_item["submitter"] == "Alice"
    assert spot_item["spot"]["city"] == "Ikogosi"
    assert spot_item["spot"]["latitude"] == pytest.approx(7.5833)
    assert spot_item["photo_url"] is None
    assert photo_item["submitter"] == "Alice" and photo_item["spot_slug"] == "live-spot"
    assert photo_item["photo_url"].endswith("/spots/waiting") and photo_item["spot"] is None


async def test_cors_preflight_allows_the_moderation_methods(client: httpx.AsyncClient) -> None:
    for method in ("PATCH", "DELETE"):
        response = await client.options(
            f"/api/spots/{uuid.uuid4()}",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert response.status_code == 200, method
        assert method in response.headers["access-control-allow-methods"]


async def test_moderation_writes_fall_under_the_ip_rate_limit() -> None:
    settings: Settings = make_settings(write_rate_limit_per_minute=2)
    app = create_app(settings, token_verifier=FakeVerifier(), rate_limit_overrides={})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        codes = [
            (await c.patch(f"/api/spots/{uuid.uuid4()}", json=APPROVE)).status_code
            for _ in range(3)
        ]
    assert codes == [401, 401, 429]
    await app.state.engine.dispose()
