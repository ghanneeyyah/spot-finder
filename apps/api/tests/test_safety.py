import asyncio
from collections.abc import Callable

import httpx
import pytest
from app.models import SafetyReport, User
from app.services.safety_service import decide_tier
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import add_spot, auth


async def report(
    client: httpx.AsyncClient, spot_id: object, tier: str, token: str
) -> httpx.Response:
    return await client.post(
        "/api/safety-reports",
        json={"spot_id": str(spot_id), "reported_tier": tier, "comment": "  looked fine  "},
        headers=auth(token),
    )


def test_decide_tier_majority_with_cautious_ties() -> None:
    assert decide_tier({}) == "unverified"
    assert decide_tier({"green": 2, "red": 1}) == "green"
    assert decide_tier({"green": 1, "red": 1}) == "red"
    assert decide_tier({"green": 1, "yellow": 1}) == "yellow"
    assert decide_tier({"green": 1, "yellow": 1, "red": 1}) == "red"
    assert decide_tier({"green": 0, "yellow": 0, "red": 3}) == "red"


async def test_requires_authentication(client: httpx.AsyncClient, db: AsyncSession) -> None:
    spot = await add_spot(db)
    response = await client.post(
        "/api/safety-reports", json={"spot_id": str(spot.id), "reported_tier": "green"}
    )
    assert response.status_code == 401


async def test_report_updates_tier_and_count(client: httpx.AsyncClient, db: AsyncSession) -> None:
    spot = await add_spot(db, "Reported Spot")
    created = await report(client, spot.id, "green", "tok-alice")
    assert created.status_code == 201
    assert created.json()["comment"] == "looked fine"
    assert set(created.json()) == {"id", "reported_tier", "comment", "created_at"}

    detail = (await client.get("/api/spots/reported-spot")).json()
    assert (detail["display_tier"], detail["safety_report_count"]) == ("green", 1)

    await report(client, spot.id, "red", "tok-bob")  # 1 green vs 1 red: cautious tie-break
    detail = (await client.get("/api/spots/reported-spot")).json()
    assert (detail["display_tier"], detail["safety_report_count"]) == ("red", 2)


async def test_one_report_per_user_per_spot(client: httpx.AsyncClient, db: AsyncSession) -> None:
    spot = await add_spot(db)
    assert (await report(client, spot.id, "green", "tok-alice")).status_code == 201
    again = await report(client, spot.id, "red", "tok-alice")
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_reported"


async def test_report_validation_and_missing_spot(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    spot = await add_spot(db)
    assert (await report(client, spot.id, "unverified", "tok-alice")).status_code == 422
    missing = await report(client, "00000000-0000-0000-0000-000000000000", "green", "tok-alice")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "spot_not_found"
    hidden = await add_spot(db, "Hidden", is_active=False)
    assert (await report(client, hidden.id, "green", "tok-alice")).status_code == 404
    bad = await client.post(
        "/api/safety-reports",
        json={"spot_id": "not-a-uuid", "reported_tier": "green"},
        headers=auth("tok-alice"),
    )
    assert bad.status_code == 422


async def test_list_reports_is_public_paginated_and_anonymous(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    spot = await add_spot(db)
    await report(client, spot.id, "green", "tok-alice")
    await report(client, spot.id, "yellow", "tok-bob")
    body = (await client.get(f"/api/safety-reports/{spot.id}")).json()
    assert (body["total"], body["limit"], body["offset"]) == (2, 20, 0)
    assert all(
        set(item) == {"id", "reported_tier", "comment", "created_at"} for item in body["items"]
    )
    page = (await client.get(f"/api/safety-reports/{spot.id}?limit=1&offset=1")).json()
    assert len(page["items"]) == 1 and page["total"] == 2
    assert (await client.get(f"/api/safety-reports/{spot.id}?limit=101")).status_code == 422
    assert (await client.get("/api/safety-reports/not-a-uuid")).status_code == 422
    missing = await client.get("/api/safety-reports/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404


async def test_simultaneous_duplicate_reports_cannot_both_succeed(
    make_client: Callable[..., httpx.AsyncClient], db: AsyncSession
) -> None:
    spot = await add_spot(db)
    payload = {"spot_id": str(spot.id), "reported_tier": "green"}

    async def submit() -> int:
        async with make_client() as c:
            return (
                await c.post("/api/safety-reports", json=payload, headers=auth("tok-alice"))
            ).status_code

    # Warm up the account so both requests race on the report insert, not on user creation.
    async with make_client() as c:
        await c.get("/api/admin/moderation-queue", headers=auth("tok-alice"))
    codes = sorted(await asyncio.gather(*(submit() for _ in range(6))))
    assert codes.count(201) == 1 and codes.count(409) == 5


async def test_database_rejects_duplicate_reports_directly(db: AsyncSession) -> None:
    spot = await add_spot(db)
    user = User(firebase_uid="dup-user")
    db.add(user)
    await db.flush()
    db.add(SafetyReport(spot_id=spot.id, user_id=user.id, reported_tier="green"))
    await db.commit()
    db.add(SafetyReport(spot_id=spot.id, user_id=user.id, reported_tier="red"))
    with pytest.raises(IntegrityError):
        await db.commit()
