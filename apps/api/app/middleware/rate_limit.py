import math
import time
from collections.abc import Callable
from dataclasses import dataclass

from starlette.types import ASGIApp, Receive, Scope, Send

from app.middleware.error_handler import error_response

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@dataclass(frozen=True)
class Rule:
    limit: int
    window_seconds: int


class FixedWindowLimiter:
    """In-memory fixed-window counters.

    State is per process: with N gunicorn workers the effective limit is up to N times the rule.
    Swap the storage for Redis when the first bottleneck appears; the interface stays the same.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic, max_keys: int = 50_000) -> None:
        self._clock = clock
        self._max_keys = max_keys
        self._windows: dict[str, tuple[float, int, int]] = {}  # key -> (start, window, count)

    def hit(self, key: str, rule: Rule) -> int | None:
        """Count one request. Returns seconds to wait if the limit is exceeded, else None."""
        now = self._clock()
        entry = self._windows.get(key)
        if entry is None or now >= entry[0] + entry[1]:
            if len(self._windows) >= self._max_keys:
                self._purge(now)
            self._windows[key] = (now, rule.window_seconds, 1)
            return None
        start, window, count = entry
        if count >= rule.limit:
            return max(1, math.ceil(start + window - now))
        self._windows[key] = (start, window, count + 1)
        return None

    def _purge(self, now: float) -> None:
        self._windows = {k: v for k, v in self._windows.items() if now < v[0] + v[1]}
        if len(self._windows) >= self._max_keys:  # still full: drop the oldest half
            for key in list(self._windows)[: len(self._windows) // 2]:
                del self._windows[key]


def client_ip(scope: Scope, trusted_proxy_count: int) -> str:
    client = scope.get("client")
    peer = str(client[0]) if client else "unknown"
    if trusted_proxy_count <= 0:
        return peer
    forwarded: str = dict(scope["headers"]).get(b"x-forwarded-for", b"").decode("latin-1")
    hops = [h.strip() for h in forwarded.split(",") if h.strip()]
    # Each trusted proxy appends the address it saw, so count from the right: anything further
    # left is client-controlled and could be forged.
    if len(hops) >= trusted_proxy_count:
        return hops[-trusted_proxy_count]
    return peer


class RateLimitMiddleware:
    """Per-IP limit on every write request (POST/PUT/PATCH/DELETE), applied by method so a new
    write route can never ship unprotected. Paths in `overrides` get their own stricter rule.
    Reads and CORS preflights are not limited. A per-user limit is applied after auth in
    dependencies.user_rate_limit because many mobile users share one carrier IP."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        limiter: FixedWindowLimiter,
        default: Rule,
        overrides: dict[tuple[str, str], Rule],
        trusted_proxy_count: int = 0,
    ) -> None:
        self.app = app
        self.limiter = limiter
        self.default = default
        self.overrides = overrides
        self.trusted_proxy_count = trusted_proxy_count

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in WRITE_METHODS:
            await self.app(scope, receive, send)
            return
        route = (scope["method"], scope["path"])
        rule = self.overrides.get(route, self.default)
        bucket = f"{route[0]} {route[1]}" if route in self.overrides else "default"
        ip = client_ip(scope, self.trusted_proxy_count)
        retry_after = self.limiter.hit(f"ip:{ip}:{bucket}", rule)
        if retry_after is not None:
            response = error_response(
                429,
                "rate_limited",
                "Too many requests. Try again later.",
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
