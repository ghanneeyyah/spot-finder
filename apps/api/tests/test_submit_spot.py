import httpx
from app.models import Spot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth

VALID = {
    "name": "Ọbalende Market Walk",
    "category": "hangout",
    "state": "lagos",
    "city": "Lagos Island",
    "latitude": 6.4541,
    "longitude": 3.3792,
    "amenities": {"parking": True},
}


async def test_requires_authentication(client: httpx.AsyncClient) -> None:
    missing = await client.post("/api/spots", json=VALID)
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "not_authenticated"
    assert missing.headers["www-authenticate"] == "Bearer"
    bad = await client.post("/api/spots", json=VALID, headers=auth("nonsense"))
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "invalid_token"
    wrong_scheme = await client.post(
        "/api/spots", json=VALID, headers={"Authorization": "Basic abc"}
    )
    assert wrong_scheme.status_code == 401


async def test_creates_hidden_pending_spot(client: httpx.AsyncClient, db: AsyncSession) -> None:
    response = await client.post("/api/spots", json=VALID, headers=auth("tok-alice"))
    assert response.status_code == 201
    body = response.json()
    assert body["slug"] == "obalende-market-walk" and body["status"] == "pending_review"
    spot = (await db.execute(select(Spot).where(Spot.slug == body["slug"]))).scalar_one()
    assert (spot.is_active, spot.is_verified, spot.safety_tier) == (False, False, "unverified")
    assert spot.state == "Lagos"  # canonicalised
    assert (await client.get("/api/spots")).json()["total"] == 0
    assert (await client.get(f"/api/spots/{body['slug']}")).status_code == 404


async def test_duplicate_names_get_distinct_slugs(client: httpx.AsyncClient) -> None:
    first = await client.post("/api/spots", json=VALID, headers=auth("tok-alice"))
    second = await client.post("/api/spots", json=VALID, headers=auth("tok-alice"))
    assert first.json()["slug"] == "obalende-market-walk"
    assert second.json()["slug"] == "obalende-market-walk-2"


async def test_server_side_validation(client: httpx.AsyncClient) -> None:
    cases = {
        "outside nigeria": {**VALID, "latitude": 51.5, "longitude": -0.1},
        "swapped coordinates": {**VALID, "latitude": 3.3792, "longitude": 6.4541},
        "unknown state": {**VALID, "state": "Atlantis"},
        "bad category": {**VALID, "category": "casino"},
        "extra field": {**VALID, "is_active": True},
        "short name": {**VALID, "name": "x"},
        "long description": {**VALID, "description": "x" * 2001},
        "bad amenity key": {**VALID, "amenities": {"Free WiFi!": True}},
        "non-bool amenity": {**VALID, "amenities": {"parking": "yes"}},
    }
    for label, payload in cases.items():
        response = await client.post("/api/spots", json=payload, headers=auth("tok-alice"))
        assert response.status_code == 422, label
        error = response.json()["error"]
        assert error["code"] == "validation_error" and error["details"], label
        assert all(set(d) == {"field", "message", "type"} for d in error["details"])


async def test_validation_errors_never_echo_input(client: httpx.AsyncClient) -> None:
    secret = "SECRET-VALUE-123"
    response = await client.post(
        "/api/spots", json={**VALID, "category": secret}, headers=auth("tok-alice")
    )
    assert response.status_code == 422 and secret not in response.text


async def test_malformed_json_is_a_422(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/spots",
        content=b"{not json",
        headers={**auth("tok-alice"), "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
