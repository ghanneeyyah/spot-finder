import asyncio
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx
from google.auth import exceptions as google_exceptions
from google.auth import jwt

log = logging.getLogger("app.auth")

# Public signing certificates for Firebase ID tokens. No credentials are needed to verify.
CERTS_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
)
_MAX_AGE = re.compile(r"max-age=(\d+)")


@dataclass(frozen=True)
class AuthClaims:
    uid: str
    email: str | None
    name: str | None


class TokenInvalid(Exception):
    """The token is malformed, expired, or not meant for this project."""


class AuthUnavailable(Exception):
    """Verification could not run (certificates unreachable, or auth not configured)."""


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> AuthClaims: ...


class UnconfiguredVerifier:
    async def verify(self, token: str) -> AuthClaims:
        raise AuthUnavailable("FIREBASE_PROJECT_ID is not configured")


class FirebaseTokenVerifier:
    """Verifies Firebase ID tokens: RS256 signature against Google's published certificates,
    plus audience, issuer, subject, and expiry checks."""

    def __init__(
        self,
        project_id: str,
        http: httpx.AsyncClient | None = None,
        certs_url: str = CERTS_URL,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._project_id = project_id
        self._http = http or httpx.AsyncClient(timeout=5.0)
        self._certs_url = certs_url
        self._clock = clock
        self._certs: dict[str, str] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get_certs(self) -> dict[str, str]:
        async with self._lock:
            now = self._clock()
            if self._certs and now < self._expires_at:
                return self._certs
            try:
                response = await self._http.get(self._certs_url)
                response.raise_for_status()
                certs = response.json()
                if not isinstance(certs, dict) or not certs:
                    raise ValueError("unexpected certificate payload")
            except (httpx.HTTPError, ValueError) as exc:
                if self._certs:  # keep serving with the stale set rather than failing every request
                    log.warning("certificate refresh failed; using cached certificates")
                    return self._certs
                raise AuthUnavailable("could not fetch Firebase certificates") from exc
            match = _MAX_AGE.search(response.headers.get("cache-control", ""))
            max_age = int(match.group(1)) if match else 3600
            self._certs = {str(k): str(v) for k, v in certs.items()}
            self._expires_at = now + min(max(max_age, 60), 86_400)
            return self._certs

    async def verify(self, token: str) -> AuthClaims:
        certs = await self._get_certs()
        try:
            claims = await asyncio.to_thread(
                jwt.decode, token, certs=certs, audience=self._project_id, clock_skew_in_seconds=10
            )
        except (ValueError, google_exceptions.GoogleAuthError) as exc:
            raise TokenInvalid(str(exc)) from exc

        if claims.get("iss") != f"https://securetoken.google.com/{self._project_id}":
            raise TokenInvalid("wrong issuer")
        sub = claims.get("sub")
        if not isinstance(sub, str) or not 0 < len(sub) <= 128:
            raise TokenInvalid("missing subject")
        auth_time = claims.get("auth_time")
        if not isinstance(auth_time, int | float) or auth_time > self._clock() + 10:
            raise TokenInvalid("invalid auth_time")

        email = claims.get("email")
        name = claims.get("name")
        return AuthClaims(
            uid=sub,
            email=email if isinstance(email, str) else None,
            name=name if isinstance(name, str) else None,
        )
