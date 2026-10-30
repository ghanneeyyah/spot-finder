import httpx
import pytest
from app.main import create_app
from fastapi import FastAPI

from tests.conftest import FakeVerifier, make_settings

EXPECTED_ENDPOINTS = {
    ("GET", "/api/health"),
    ("GET", "/api/spots"),
    ("GET", "/api/spots/{slug}"),
    ("GET", "/api/spots/nearby"),
    ("POST", "/api/spots"),
    ("POST", "/api/safety-reports"),
    ("GET", "/api/safety-reports/{spot_id}"),
    ("POST", "/api/photos"),
    ("GET", "/api/admin/moderation-queue"),
}


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_exactly_the_specified_endpoints_exist(client: httpx.AsyncClient) -> None:
    schema = (await client.get("/api/openapi.json")).json()
    found = {
        (method.upper(), path)
        for path, operations in schema["paths"].items()
        for method in operations
    }
    assert found == EXPECTED_ENDPOINTS


async def test_unknown_route_and_method_use_the_error_shape(client: httpx.AsyncClient) -> None:
    missing = await client.get("/api/nothing-here")
    assert missing.status_code == 404
    assert missing.json() == {"error": {"code": "not_found", "message": "Resource not found."}}
    wrong_method = await client.put("/api/spots/some-slug", json={})
    assert wrong_method.status_code == 405
    assert wrong_method.json()["error"]["code"] == "method_not_allowed"


async def test_request_id_is_generated_and_echoed(client: httpx.AsyncClient) -> None:
    generated = await client.get("/api/health")
    assert len(generated.headers["x-request-id"]) == 32
    echoed = await client.get("/api/health", headers={"X-Request-ID": "trace-abc-12345"})
    assert echoed.headers["x-request-id"] == "trace-abc-12345"
    hostile = await client.get("/api/health", headers={"X-Request-ID": "bad id\twith spaces"})
    assert hostile.headers["x-request-id"] != "bad id\twith spaces"


async def test_unhandled_errors_do_not_leak_internals(app: FastAPI, make_client) -> None:  # type: ignore[no-untyped-def]
    async def boom() -> None:
        raise RuntimeError("SECRET-INTERNAL-DETAIL /srv/app/secrets.py")

    app.add_api_route("/api/boom", boom)
    async with make_client(raise_exceptions=False) as c:
        response = await c.get("/api/boom", headers={"Origin": "https://app.example.com"})
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Something went wrong on our side."}
    }
    for leaked in ("SECRET-INTERNAL-DETAIL", "Traceback", "secrets.py", "RuntimeError"):
        assert leaked not in response.text
    assert response.headers["x-request-id"]
    assert response.headers["access-control-allow-origin"] == "https://app.example.com"


async def test_docs_are_hidden_in_production() -> None:
    settings = make_settings(environment="production")
    app = create_app(settings, token_verifier=FakeVerifier())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        assert (await c.get("/api/openapi.json")).status_code == 404
        assert (await c.get("/api/docs")).status_code == 404
    await app.state.engine.dispose()


@pytest.mark.parametrize(
    "origin,allowed", [("https://app.example.com", True), ("https://evil.example", False)]
)
async def test_cors_only_allows_configured_origins(
    client: httpx.AsyncClient, origin: str, allowed: bool
) -> None:
    preflight = await client.options(
        "/api/spots",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    header = preflight.headers.get("access-control-allow-origin")
    assert (header == origin) if allowed else (header is None)
    assert header != "*"
    plain = await client.get("/api/health", headers={"Origin": origin})
    assert plain.headers.get("access-control-allow-credentials") is None
