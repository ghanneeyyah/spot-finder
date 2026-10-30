import httpx
import pytest
from app.models import SpotPhoto
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import add_spot, auth


@pytest.mark.usefixtures("staff")
async def test_queue_requires_a_moderator(client: httpx.AsyncClient) -> None:
    url = "/api/admin/moderation-queue"
    assert (await client.get(url)).status_code == 401
    assert (await client.get(url, headers=auth("nonsense"))).status_code == 401
    forbidden = await client.get(url, headers=auth("tok-alice"))
    assert forbidden.status_code == 403 and forbidden.json()["error"]["code"] == "forbidden"
    disabled = await client.get(url, headers=auth("tok-disabled"))
    assert disabled.status_code == 403 and disabled.json()["error"]["code"] == "account_disabled"
    assert (await client.get(url, headers=auth("tok-mod"))).status_code == 200
    assert (await client.get(url, headers=auth("tok-admin"))).status_code == 200


@pytest.mark.usefixtures("staff")
async def test_queue_lists_only_pending_items_oldest_first(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    pending = await add_spot(db, "Pending Spot", is_active=False, is_verified=False)
    live = await add_spot(db, "Live Spot")
    db.add(SpotPhoto(spot_id=live.id, cloudinary_public_id="spots/waiting", is_approved=False))
    db.add(SpotPhoto(spot_id=live.id, cloudinary_public_id="spots/done", is_approved=True))
    await db.commit()

    body = (await client.get("/api/admin/moderation-queue", headers=auth("tok-mod"))).json()
    assert (body["total"], body["limit"], body["offset"]) == (2, 20, 0)
    spot_item, photo_item = body["items"]
    assert spot_item["kind"] == "spot" and spot_item["spot_id"] == str(pending.id)
    assert spot_item["photo_url"] is None
    assert photo_item["kind"] == "photo" and photo_item["spot_name"] == "Live Spot"
    assert photo_item["photo_url"].endswith("/spots/waiting")

    page = (
        await client.get("/api/admin/moderation-queue?limit=1&offset=1", headers=auth("tok-mod"))
    ).json()
    assert page["total"] == 2 and [i["kind"] for i in page["items"]] == ["photo"]
    limit = await client.get("/api/admin/moderation-queue?limit=101", headers=auth("tok-mod"))
    assert limit.status_code == 422


@pytest.mark.usefixtures("staff")
async def test_roles_come_from_the_database_not_the_token(client: httpx.AsyncClient) -> None:
    # tok-alice maps to a brand-new account, which is created with the default 'user' role.
    response = await client.get("/api/admin/moderation-queue", headers=auth("tok-alice"))
    assert response.status_code == 403
