import time

import httpx
import pytest
from app.services.firebase_auth import AuthUnavailable, FirebaseTokenVerifier, TokenInvalid

from tests.helpers import (
    SigningMaterial,
    certs_client,
    make_signing_material,
    mint_token,
    unsigned_token,
)


@pytest.fixture(scope="module")
def material() -> SigningMaterial:
    return make_signing_material()


def verifier(material: SigningMaterial, **kwargs: object) -> FirebaseTokenVerifier:
    return FirebaseTokenVerifier("test-project", http=certs_client(material, **kwargs))  # type: ignore[arg-type]


async def test_valid_token_yields_claims(material: SigningMaterial) -> None:
    token = mint_token(material, uid="uid-1", email="a@example.com", name="Ada")
    claims = await verifier(material).verify(token)
    assert (claims.uid, claims.email, claims.name) == ("uid-1", "a@example.com", "Ada")


@pytest.mark.parametrize(
    "overrides",
    [
        {"expires_in": -3600},
        {"audience": "some-other-project"},
        {"issuer": "https://securetoken.google.com/some-other-project"},
        {"issuer": "https://evil.example"},
        {"omit": ("sub",)},
        {"uid": ""},
        {"auth_time_offset": 3600},
        {"omit": ("auth_time",)},
    ],
)
async def test_bad_claims_are_rejected(
    material: SigningMaterial, overrides: dict[str, object]
) -> None:
    with pytest.raises(TokenInvalid):
        await verifier(material).verify(mint_token(material, **overrides))  # type: ignore[arg-type]


async def test_token_signed_by_an_unknown_key_is_rejected(material: SigningMaterial) -> None:
    attacker = make_signing_material(kid=material.kid)  # same kid, different key
    with pytest.raises(TokenInvalid):
        await verifier(material).verify(mint_token(attacker))


async def test_garbage_and_unsigned_tokens_are_rejected(material: SigningMaterial) -> None:
    v = verifier(material)
    for token in ("", "garbage", "a.b.c", unsigned_token({"sub": "x", "aud": "test-project"})):
        with pytest.raises(TokenInvalid):
            await v.verify(token)


async def test_certificates_are_cached_between_calls(material: SigningMaterial) -> None:
    calls: list[str] = []
    v = verifier(material, calls=calls)
    for _ in range(3):
        await v.verify(mint_token(material))
    assert len(calls) == 1


async def test_certificate_outage_is_unavailable_not_invalid(material: SigningMaterial) -> None:
    with pytest.raises(AuthUnavailable):
        await verifier(material, status=503).verify(mint_token(material))


async def test_stale_certificates_keep_working_during_an_outage(material: SigningMaterial) -> None:
    now = [time.time()]
    state = {"up": True}

    def handler(request: httpx.Request) -> httpx.Response:
        if not state["up"]:
            return httpx.Response(503)
        return httpx.Response(
            200, json={material.kid: material.cert_pem}, headers={"cache-control": "max-age=60"}
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    v = FirebaseTokenVerifier("test-project", http=http, clock=lambda: now[0])
    token = mint_token(material, uid="u")
    await v.verify(token)
    state["up"] = False
    now[0] += 600  # cache expired
    assert (await v.verify(token)).uid == "u"
