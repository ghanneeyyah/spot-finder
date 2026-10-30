from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from app.config import Settings
from app.main import create_app
from pydantic import ValidationError

from tests.conftest import FakeVerifier, make_settings

DB = "postgresql://u:p@localhost/db"


def build(**values: Any) -> Settings:
    """Settings with untyped kwargs, so tests can pass deliberately invalid values."""
    return Settings(**values)


PROD: dict[str, Any] = {
    "environment": "production",
    "firebase_project_id": "proj",
    "cloudinary_cloud_name": "c",
    "cloudinary_api_key": "k",
    "cloudinary_api_secret": "s",
}


def test_cors_wildcard_is_rejected_everywhere() -> None:
    for environment in ("development", "production"):
        with pytest.raises(ValidationError):
            build(
                database_url=DB,
                environment=environment,
                cors_origins=["*"],
                **{k: v for k, v in PROD.items() if k != "environment"},
            )


def test_cors_origins_parse_from_a_comma_separated_string() -> None:
    settings = build(database_url=DB, cors_origins="https://a.com, https://b.com/")
    assert settings.cors_origins == ["https://a.com", "https://b.com"]


def test_malformed_origins_are_rejected() -> None:
    for bad in ("https://a.com/path", "a.com", "https://"):
        with pytest.raises(ValidationError):
            build(database_url=DB, cors_origins=[bad])


def test_production_requires_https_origins_and_all_secrets() -> None:
    build(database_url=DB, cors_origins=["https://app.example.com"], **PROD)
    with pytest.raises(ValidationError, match="https"):
        build(database_url=DB, cors_origins=["http://app.example.com"], **PROD)
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        build(database_url=DB, cors_origins=[], **PROD)
    for missing in ("firebase_project_id", "cloudinary_cloud_name", "cloudinary_api_key"):
        values = {k: v for k, v in PROD.items() if k != missing}
        with pytest.raises(ValidationError, match="Missing required production settings"):
            build(database_url=DB, cors_origins=["https://app.example.com"], **values)


def test_database_url_is_forced_onto_asyncpg() -> None:
    assert build(database_url="postgres://u:p@h/db").database_url.startswith(
        "postgresql+asyncpg://"
    )
    assert build(database_url="postgresql://u:p@h/db").database_url.startswith(
        "postgresql+asyncpg://"
    )


def test_secrets_are_not_printed() -> None:
    settings = build(database_url=DB, cloudinary_api_secret="topsecret")
    assert "topsecret" not in repr(settings)


async def test_oversized_json_is_rejected_before_parsing(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/spots",
        content=b'{"name": "' + b"x" * 70_000 + b'"}',
        headers={"Content-Type": "application/json", "Authorization": "Bearer tok-alice"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


async def test_oversized_chunked_body_is_cut_off() -> None:
    app = create_app(make_settings(), token_verifier=FakeVerifier(), rate_limit_overrides={})

    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(20):
            yield b"x" * 8192

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        response = await c.post(
            "/api/spots",
            content=chunks(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer tok-alice"},
        )
    assert response.status_code == 413
    await app.state.engine.dispose()


def test_page_and_slug_helpers() -> None:
    from app.utils.geo import parse_bbox
    from app.utils.slug import slugify

    assert slugify("Ọbalende Market!") == "obalende-market"
    assert slugify("!!!") == "spot"
    assert len(slugify("a" * 500)) <= 80
    assert parse_bbox("2.6,4.2,14.7,13.9").max_lat == 13.9
