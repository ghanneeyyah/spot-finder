"""Test helpers: self-signed Firebase-style tokens and a fake certificate endpoint."""

import base64
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from google.auth import crypt, jwt


@dataclass(frozen=True)
class SigningMaterial:
    private_pem: bytes
    cert_pem: str
    kid: str


def make_signing_material(kid: str = "test-kid") -> SigningMaterial:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "spotfinder-test")])
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return SigningMaterial(
        private_pem=private_pem,
        cert_pem=cert.public_bytes(serialization.Encoding.PEM).decode(),
        kid=kid,
    )


def mint_token(
    material: SigningMaterial,
    *,
    project_id: str = "test-project",
    uid: str = "alice",
    email: str | None = None,
    name: str | None = None,
    issuer: str | None = None,
    audience: str | None = None,
    expires_in: int = 3600,
    auth_time_offset: int = 0,
    omit: tuple[str, ...] = (),
) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "iss": issuer or f"https://securetoken.google.com/{project_id}",
        "aud": audience or project_id,
        "sub": uid,
        "iat": now - 5,
        "exp": now + expires_in,
        "auth_time": now + auth_time_offset,
    }
    if email:
        payload["email"] = email
    if name:
        payload["name"] = name
    for claim in omit:
        payload.pop(claim, None)
    signer: Any = crypt.RSASigner.from_string(material.private_pem, key_id=material.kid)  # type: ignore[no-untyped-call]
    token = jwt.encode(signer, payload)  # type: ignore[no-untyped-call]
    return token.decode() if isinstance(token, bytes) else str(token)


def unsigned_token(payload: dict[str, Any]) -> str:
    def part(data: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'none', 'typ': 'JWT'})}.{part(payload)}."


def certs_client(
    material: SigningMaterial,
    *,
    calls: list[str] | None = None,
    status: int = 200,
    max_age: int = 3600,
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(
            200,
            json={material.kid: material.cert_pem},
            headers={"cache-control": f"public, max-age={max_age}"},
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))
