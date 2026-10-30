import httpx
from app.models import SpotPhoto
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import JPEG, FakeUploader, add_spot, auth


async def upload(
    client: httpx.AsyncClient, spot_id: object, data: bytes = JPEG, as_user: str = "tok-alice"
) -> httpx.Response:
    return await client.post(
        "/api/photos",
        data={"spot_id": str(spot_id)},
        files={"file": ("photo.jpg", data, "image/jpeg")},
        headers=auth(as_user),
    )


async def test_requires_authentication(client: httpx.AsyncClient, db: AsyncSession) -> None:
    spot = await add_spot(db)
    response = await client.post(
        "/api/photos",
        data={"spot_id": str(spot.id)},
        files={"file": ("p.jpg", JPEG, "image/jpeg")},
    )
    assert response.status_code == 401


async def test_upload_is_stored_pending_moderation(
    client: httpx.AsyncClient, db: AsyncSession, uploader: FakeUploader
) -> None:
    spot = await add_spot(db, "Photo Spot")
    response = await upload(client, spot.id)
    assert response.status_code == 201 and response.json()["status"] == "pending_review"
    assert uploader.uploads == [(len(JPEG), "spots")]
    photo = (await db.execute(select(SpotPhoto))).scalar_one()
    assert photo.is_approved is False and photo.cloudinary_public_id.startswith("spots/fake-")
    assert (await client.get("/api/spots/photo-spot")).json()["photos"] == []


async def test_content_is_sniffed_not_trusted(
    client: httpx.AsyncClient, db: AsyncSession, uploader: FakeUploader
) -> None:
    spot = await add_spot(db)
    response = await upload(client, spot.id, b"<?php echo 'not an image'; ?>")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type" and not uploader.uploads
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    webp = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 8
    assert (await upload(client, spot.id, png)).status_code == 201
    assert (await upload(client, spot.id, webp, "tok-bob")).status_code == 201


async def test_oversized_image_is_rejected(client: httpx.AsyncClient, db: AsyncSession) -> None:
    spot = await add_spot(db)
    response = await upload(client, spot.id, JPEG + b"\x00" * (5 * 1024 * 1024))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


async def test_unknown_spot_and_bad_input(client: httpx.AsyncClient, db: AsyncSession) -> None:
    missing = await upload(client, "00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
    hidden = await add_spot(db, "Hidden", is_active=False)
    assert (await upload(client, hidden.id)).status_code == 404
    no_file = await client.post("/api/photos", data={"spot_id": "x"}, headers=auth("tok-alice"))
    assert no_file.status_code == 422


async def test_upload_failure_is_a_clean_502(
    client: httpx.AsyncClient, db: AsyncSession, uploader: FakeUploader
) -> None:
    spot = await add_spot(db)
    uploader.fail = True
    response = await upload(client, spot.id)
    assert response.status_code == 502 and response.json()["error"]["code"] == "upload_failed"
    assert (await db.execute(select(SpotPhoto))).first() is None
