import httpx
from app.models import SafetyReport, SpotPhoto, User
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import add_spot


async def test_list_returns_pagination_envelope(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    for n in range(3):
        await add_spot(db, f"Spot {n}")
    body = (await client.get("/api/spots")).json()
    assert (body["total"], body["limit"], body["offset"]) == (3, 20, 0)
    assert len(body["items"]) == 3


async def test_pages_do_not_overlap_and_cover_everything(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    for n in range(25):
        await add_spot(db, f"Spot {n:02d}")
    first = (await client.get("/api/spots")).json()
    second = (await client.get("/api/spots?offset=20")).json()
    assert len(first["items"]) == 20 and len(second["items"]) == 5
    assert first["total"] == second["total"] == 25
    slugs = [i["slug"] for i in first["items"] + second["items"]]
    assert len(set(slugs)) == 25


async def test_limit_bounds_are_enforced(client: httpx.AsyncClient) -> None:
    for query in ("limit=101", "limit=0", "offset=-1"):
        response = await client.get(f"/api/spots?{query}")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
    assert (await client.get("/api/spots?limit=100")).status_code == 200


def names(response: httpx.Response) -> list[str]:
    return sorted(i["name"] for i in response.json()["items"])


async def test_filters(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await add_spot(db, "Beach One", category="beach", state="Lagos", city="Lagos")
    await add_spot(db, "Rock One", category="nature", state="Ogun", city="Abeokuta", tier="green")
    await add_spot(db, "Hidden", is_active=False)
    assert names(await client.get("/api/spots")) == ["Beach One", "Rock One"]
    assert names(await client.get("/api/spots?state=Ogun")) == ["Rock One"]
    assert names(await client.get("/api/spots?city=Lagos")) == ["Beach One"]
    assert names(await client.get("/api/spots?category=beach")) == ["Beach One"]
    assert names(await client.get("/api/spots?safety_tier=green")) == ["Rock One"]
    assert (await client.get("/api/spots?category=bogus")).status_code == 422


async def test_search_matches_name_and_city_and_escapes_wildcards(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    await add_spot(db, "Alpha Park", city="Jos")
    await add_spot(db, "100% Fun", slug="fun")
    assert [i["name"] for i in (await client.get("/api/spots?q=alpha")).json()["items"]] == [
        "Alpha Park"
    ]
    assert [i["name"] for i in (await client.get("/api/spots?q=jos")).json()["items"]] == [
        "Alpha Park"
    ]
    assert [i["name"] for i in (await client.get("/api/spots?q=%25")).json()["items"]] == [
        "100% Fun"
    ]


async def test_bbox_filter_and_validation(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await add_spot(db, "Lagos Spot", lat=6.45, lng=3.38)
    await add_spot(db, "Jos Spot", lat=9.85, lng=8.87)
    inside = (await client.get("/api/spots?bbox=3,6,4,7")).json()
    assert [i["name"] for i in inside["items"]] == ["Lagos Spot"] and inside["total"] == 1
    for bad in ("1,2,3", "a,b,c,d", "4,6,3,7", "3,7,4,6", "-200,0,1,1"):
        response = await client.get(f"/api/spots?bbox={bad}")
        assert response.status_code == 422, bad
        assert response.json()["error"]["details"][0]["field"] == "query.bbox"


async def test_stored_tier_is_hidden_until_reports_exist(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    await add_spot(db, "Stored Green", tier="green", score=8.0)
    item = (await client.get("/api/spots")).json()["items"][0]
    assert item["display_tier"] == "unverified" and item["safety_report_count"] == 0


async def test_nearby_orders_by_distance_in_meters(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    await add_spot(db, "Far", lat=6.6018, lng=3.3426)  # Ikeja, ~17 km from Lagos Island
    await add_spot(db, "Near", lat=6.4600, lng=3.3800)
    await add_spot(db, "Out Of Range", lat=9.85, lng=8.87)
    body = (await client.get("/api/spots/nearby?lat=6.4541&lng=3.3792&radius_km=30")).json()
    assert [i["name"] for i in body["items"]] == ["Near", "Far"]
    assert body["total"] == 2
    assert 600 < body["items"][0]["distance_m"] < 1000
    assert 15_000 < body["items"][1]["distance_m"] < 19_000
    narrow = (await client.get("/api/spots/nearby?lat=6.4541&lng=3.3792&radius_km=5")).json()
    assert [i["name"] for i in narrow["items"]] == ["Near"]


async def test_nearby_validates_input(client: httpx.AsyncClient) -> None:
    for query in (
        "lat=6.4&lng=3.4&radius_km=0",
        "lat=6.4&lng=3.4&radius_km=101",
        "lat=50&lng=3.4",
        "lat=6.4",
        "lat=nan&lng=3.4",
    ):
        assert (await client.get(f"/api/spots/nearby?{query}")).status_code == 422, query


async def test_detail_with_zero_reports(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await add_spot(db, "Quiet Spot", tier="green", score=9.0)
    body = (await client.get("/api/spots/quiet-spot")).json()
    assert body["safety_report_count"] == 0
    assert body["display_tier"] == "unverified"
    assert body["safety_score"] is None
    assert body["photos"] == []
    assert (body["latitude"], body["longitude"]) == (6.45, 3.38)


async def test_detail_with_reports_and_approved_photos_only(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    spot = await add_spot(db, "Busy Spot", tier="yellow", score=5.5)
    user = User(firebase_uid="u1")
    db.add(user)
    await db.flush()
    db.add(SafetyReport(spot_id=spot.id, user_id=user.id, reported_tier="yellow"))
    db.add(SpotPhoto(spot_id=spot.id, cloudinary_public_id="spots/ok", is_approved=True))
    db.add(SpotPhoto(spot_id=spot.id, cloudinary_public_id="spots/pending", is_approved=False))
    await db.commit()
    body = (await client.get("/api/spots/busy-spot")).json()
    assert body["safety_report_count"] == 1
    assert body["display_tier"] == body["safety_tier"] == "yellow"
    assert body["safety_score"] == 5.5
    assert [p["url"] for p in body["photos"]] == [
        "https://res.cloudinary.com/democloud/image/upload/f_auto,q_auto/spots/ok"
    ]


async def test_detail_404_and_slug_validation(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await add_spot(db, "Hidden Spot", is_active=False)
    missing = await client.get("/api/spots/hidden-spot")
    assert missing.status_code == 404
    assert missing.json() == {"error": {"code": "spot_not_found", "message": "Spot not found."}}
    assert (await client.get("/api/spots/Bad_Slug")).status_code == 422
