import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse

import httpx
import pytest
import pytest_asyncio
from app.config import Settings
from app.main import create_app
from app.middleware.rate_limit import Rule
from app.models import Spot, User
from app.services.firebase_auth import AuthClaims, TokenInvalid
from app.utils.geo import geog_point
from app.utils.slug import slugify
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

API_ROOT = Path(__file__).resolve().parent.parent
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def _test_database_url() -> str:
    """Tests TRUNCATE every table, so they only run against a database named *test*."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    if "test" not in urlparse(url).path:
        pytest.fail("TEST_DATABASE_URL must point at a database whose name contains 'test'")
    return url


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    url = _test_database_url()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env={**os.environ, "DATABASE_URL": url},
        cwd=API_ROOT,
        check=True,
    )


class FakeVerifier:
    """Maps fixed tokens to claims. The real verifier is tested separately in test_firebase_auth."""

    TOKENS: ClassVar[dict[str, AuthClaims]] = {
        "tok-alice": AuthClaims("alice", "alice@example.com", "Alice"),
        "tok-bob": AuthClaims("bob", "bob@example.com", "Bob"),
        "tok-mod": AuthClaims("mod", "mod@example.com", "Mod"),
        "tok-admin": AuthClaims("admin", "admin@example.com", "Admin"),
        "tok-disabled": AuthClaims("disabled", None, None),
    }

    async def verify(self, token: str) -> AuthClaims:
        claims = self.TOKENS.get(token)
        if claims is None:
            raise TokenInvalid("unknown token")
        return claims


class FakeUploader:
    def __init__(self) -> None:
        self.uploads: list[tuple[int, str]] = []
        self.fail = False

    async def upload(self, data: bytes, *, folder: str) -> str:
        from app.services.cloudinary_service import UploadFailed

        if self.fail:
            raise UploadFailed
        self.uploads.append((len(data), folder))
        return f"{folder}/fake-{uuid.uuid4().hex[:8]}"


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": _test_database_url(),
        "environment": "test",
        "firebase_project_id": "test-project",
        "cors_origins": ["https://app.example.com"],
        "cloudinary_cloud_name": "democloud",
        "cloudinary_api_key": "key",
        "cloudinary_api_secret": "secret",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


@pytest.fixture
def uploader() -> FakeUploader:
    return FakeUploader()


@pytest_asyncio.fixture
async def app(uploader: FakeUploader) -> AsyncIterator[object]:
    application = create_app(
        make_settings(),
        token_verifier=FakeVerifier(),
        uploader=uploader,
        rate_limit_overrides={},
    )
    async with application.state.session_factory() as session:
        await session.execute(
            text("TRUNCATE users, spots, safety_reports, spot_photos, audit_log CASCADE")
        )
        await session.commit()
    yield application
    await application.state.engine.dispose()


@pytest.fixture
def make_client(app: object) -> Callable[..., httpx.AsyncClient]:
    def build(ip: str = "198.51.100.7", *, raise_exceptions: bool = True) -> httpx.AsyncClient:
        transport = httpx.ASGITransport(
            app=app,  # type: ignore[arg-type]
            client=(ip, 5000),
            raise_app_exceptions=raise_exceptions,
        )
        return httpx.AsyncClient(transport=transport, base_url="http://testserver")

    return build


@pytest_asyncio.fixture
async def client(make_client: Callable[..., httpx.AsyncClient]) -> AsyncIterator[httpx.AsyncClient]:
    async with make_client() as c:
        yield c


@pytest_asyncio.fixture
async def db(app: object) -> AsyncIterator[AsyncSession]:
    async with app.state.session_factory() as session:  # type: ignore[attr-defined]
        yield session


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def add_user(db: AsyncSession, uid: str, role: str = "user", *, active: bool = True) -> User:
    user = User(firebase_uid=uid, role=role, is_active=active)
    db.add(user)
    await db.commit()
    return user


async def add_spot(
    db: AsyncSession,
    name: str = "Test Spot",
    *,
    lat: float = 6.45,
    lng: float = 3.38,
    category: str = "nature",
    state: str = "Lagos",
    city: str = "Lagos",
    tier: str = "unverified",
    score: float | None = None,
    is_active: bool = True,
    is_verified: bool = True,
    slug: str | None = None,
) -> Spot:
    spot = Spot(
        name=name,
        slug=slug or slugify(name),
        category=category,
        state=state,
        city=city,
        location=geog_point(lng, lat),
        safety_tier=tier,
        safety_score=score,
        is_active=is_active,
        is_verified=is_verified,
    )
    db.add(spot)
    await db.commit()
    return spot


@pytest_asyncio.fixture
async def staff(db: AsyncSession) -> None:
    await add_user(db, "mod", "moderator")
    await add_user(db, "admin", "admin")
    await add_user(db, "disabled", active=False)


__all__ = ["JPEG", "Rule", "add_spot", "add_user", "auth", "make_settings"]
