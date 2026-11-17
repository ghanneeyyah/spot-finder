import uuid
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import add_spot, auth

async def test_add_and_list_itinerary(client: httpx.AsyncClient, db: AsyncSession) -> None:
    spot = await add_spot(db, "Test Spot")
    
    # 1. Save spot
    payload = {"planned_date": "2026-12-25", "notes": "Bring sunscreen"}
    response = await client.post(f"/api/itinerary/{spot.id}", json=payload, headers=auth("tok-alice"))
    assert response.status_code == 201
    
    data = response.json()
    assert data["planned_date"] == "2026-12-25"
    assert data["notes"] == "Bring sunscreen"
    assert data["spot"]["name"] == "Test Spot"

    # 2. Prevent duplicate saves
    duplicate = await client.post(f"/api/itinerary/{spot.id}", json=payload, headers=auth("tok-alice"))
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "already_saved"

    # 3. List itinerary shows the spot
    list_resp = await client.get("/api/itinerary", headers=auth("tok-alice"))
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1
    assert list_resp.json()["items"][0]["spot_id"] == str(spot.id)


async def test_cannot_save_inactive_spot(client: httpx.AsyncClient, db: AsyncSession) -> None:
    hidden = await add_spot(db, "Hidden Spot", is_active=False)
    
    response = await client.post(f"/api/itinerary/{hidden.id}", json={}, headers=auth("tok-alice"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "spot_not_found"


async def test_idor_protection_for_updates_and_deletes(client: httpx.AsyncClient, db: AsyncSession) -> None:
    # 1. Alice saves a spot
    spot = await add_spot(db, "Alice's Hangout")
    await client.post(f"/api/itinerary/{spot.id}", json={"notes": "Alice's secret plan"}, headers=auth("tok-alice"))

    # 2. Bob tries to update Alice's itinerary entry
    bob_patch = await client.patch(f"/api/itinerary/{spot.id}", json={"notes": "Bob was here"}, headers=auth("tok-bob"))
    assert bob_patch.status_code == 404
    assert bob_patch.json()["error"]["code"] == "entry_not_found"

    # 3. Bob tries to delete Alice's itinerary entry
    bob_delete = await client.delete(f"/api/itinerary/{spot.id}", headers=auth("tok-bob"))
    assert bob_delete.status_code == 404
    
    # 4. Verify Alice's spot is completely untouched
    alice_list = await client.get("/api/itinerary", headers=auth("tok-alice"))
    assert alice_list.json()["total"] == 1
    assert alice_list.json()["items"][0]["notes"] == "Alice's secret plan"


async def test_update_and_delete_own_entry(client: httpx.AsyncClient, db: AsyncSession) -> None:
    spot = await add_spot(db)
    await client.post(f"/api/itinerary/{spot.id}", json={}, headers=auth("tok-alice"))
    
    # Update notes
    patch = await client.patch(f"/api/itinerary/{spot.id}", json={"notes": "Updated note"}, headers=auth("tok-alice"))
    assert patch.status_code == 200
    assert patch.json()["notes"] == "Updated note"

    # Delete entry
    delete = await client.delete(f"/api/itinerary/{spot.id}", headers=auth("tok-alice"))
    assert delete.status_code == 204

    # Verify it is gone
    list_resp = await client.get("/api/itinerary", headers=auth("tok-alice"))
    assert list_resp.json()["total"] == 0