import httpx
from app.main import create_app
from app.middleware.rate_limit import FixedWindowLimiter, Rule, client_ip
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import FakeVerifier, add_spot, make_settings

SUBMIT = ("POST", "/api/spots")


async def test_ip_limit_returns_429_in_the_error_shape() -> None:
    app = create_app(
        make_settings(), token_verifier=FakeVerifier(), rate_limit_overrides={SUBMIT: Rule(3, 60)}
    )
    transport = httpx.ASGITransport(app=app, client=("198.51.100.7", 1))
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        statuses = [(await c.post("/api/spots", json={})).status_code for _ in range(3)]
        assert statuses == [401, 401, 401]
        blocked = await c.post("/api/spots", json={})
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "rate_limited"
        assert 1 <= int(blocked.headers["retry-after"]) <= 60
        # Reads, health and preflights are never limited.
        for _ in range(10):
            assert (await c.get("/api/health")).status_code == 200
        assert (
            await c.options(
                "/api/spots",
                headers={
                    "Origin": "https://app.example.com",
                    "Access-Control-Request-Method": "POST",
                },
            )
        ).status_code == 200
    other = httpx.ASGITransport(app=app, client=("203.0.113.50", 1))
    async with httpx.AsyncClient(transport=other, base_url="http://t") as c2:
        assert (await c2.post("/api/spots", json={})).status_code == 401  # separate bucket
    await app.state.engine.dispose()


async def test_429_carries_cors_headers_so_browsers_can_read_it() -> None:
    app = create_app(
        make_settings(), token_verifier=FakeVerifier(), rate_limit_overrides={SUBMIT: Rule(1, 60)}
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        headers = {"Origin": "https://app.example.com"}
        await c.post("/api/spots", json={}, headers=headers)
        blocked = await c.post("/api/spots", json={}, headers=headers)
        assert blocked.status_code == 429
        assert blocked.headers["access-control-allow-origin"] == "https://app.example.com"
    await app.state.engine.dispose()


async def test_default_rule_covers_write_routes_without_an_override() -> None:
    app = create_app(
        make_settings(write_rate_limit_per_minute=2),
        token_verifier=FakeVerifier(),
        rate_limit_overrides={},
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        codes = [(await c.post("/api/photos")).status_code for _ in range(3)]
        assert codes[:2] != [429, 429] and codes[2] == 429
    await app.state.engine.dispose()


async def test_per_user_limit_applies_after_auth(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    spot = await add_spot(db)
    payload = {"spot_id": str(spot.id), "reported_tier": "green"}
    headers = {"Authorization": "Bearer tok-alice"}
    codes = [
        (await client.post("/api/safety-reports", json=payload, headers=headers)).status_code
        for _ in range(21)
    ]
    assert codes[0] == 201 and set(codes[1:20]) == {409} and codes[20] == 429
    # Another account on the same IP is unaffected.
    other = await client.post(
        "/api/safety-reports", json=payload, headers={"Authorization": "Bearer tok-bob"}
    )
    assert other.status_code == 201


def test_limiter_window_resets() -> None:
    now = [0.0]
    limiter = FixedWindowLimiter(clock=lambda: now[0])
    rule = Rule(2, 10)
    assert limiter.hit("k", rule) is None and limiter.hit("k", rule) is None
    assert limiter.hit("k", rule) == 10
    now[0] = 4.0
    assert limiter.hit("k", rule) == 6
    now[0] = 10.0
    assert limiter.hit("k", rule) is None


def test_limiter_memory_is_bounded() -> None:
    limiter = FixedWindowLimiter(clock=lambda: 0.0, max_keys=100)
    for n in range(1000):
        limiter.hit(f"k{n}", Rule(1, 60))
    assert len(limiter._windows) <= 100


def test_forwarded_for_is_only_trusted_from_the_right() -> None:
    def scope(xff: str | None) -> dict[str, object]:
        headers = [(b"x-forwarded-for", xff.encode())] if xff else []
        return {"client": ("10.0.0.1", 1), "headers": headers}

    forged = scope("6.6.6.6, 1.2.3.4")
    assert client_ip(forged, 0) == "10.0.0.1"  # no trusted proxy: header ignored
    assert client_ip(forged, 1) == "1.2.3.4"  # rightmost entry was added by our proxy
    assert client_ip(scope("1.2.3.4"), 2) == "10.0.0.1"  # fewer hops than expected: fall back
    assert client_ip(scope(None), 1) == "10.0.0.1"
