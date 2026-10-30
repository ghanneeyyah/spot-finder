from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.middleware.error_handler import AppError
from app.middleware.rate_limit import FixedWindowLimiter, Rule
from app.models import User
from app.services.firebase_auth import AuthClaims, AuthUnavailable, TokenInvalid

_BEARER = {"WWW-Authenticate": "Bearer"}
ROLE_RANK = {"user": 0, "moderator": 1, "admin": 2}

bearer_scheme = HTTPBearer(auto_error=False, description="Firebase ID token")


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


AppSettings = Annotated[Settings, Depends(get_settings_dep)]


async def _user_for(db: AsyncSession, claims: AuthClaims) -> User:
    query = select(User).where(User.firebase_uid == claims.uid)
    user = (await db.execute(query)).scalar_one_or_none()
    if user is None:
        # First sight of this Firebase account. The unique index makes concurrent first
        # requests safe.
        await db.execute(
            insert(User)
            .values(firebase_uid=claims.uid, email=claims.email, display_name=claims.name)
            .on_conflict_do_nothing(index_elements=["firebase_uid"])
        )
        await db.commit()
        user = (await db.execute(query)).scalar_one()
    return user


async def get_current_user(
    request: Request,
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Authenticate the bearer token on the server. UI checks are never relied on.

    Missing credentials and invalid or expired tokens both return 401; verification being
    unavailable returns 503. Roles come from our database, never from token claims.
    """
    if credentials is None:
        raise AppError(401, "not_authenticated", "Authentication required.", headers=_BEARER)
    try:
        claims = await request.app.state.token_verifier.verify(credentials.credentials)
    except TokenInvalid as exc:
        raise AppError(401, "invalid_token", "Invalid or expired token.", headers=_BEARER) from exc
    except AuthUnavailable as exc:
        raise AppError(503, "auth_unavailable", "Sign-in is temporarily unavailable.") from exc
    user = await _user_for(db, claims)
    if not user.is_active:
        raise AppError(403, "account_disabled", "This account is disabled.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(minimum: str) -> Callable[[User], Awaitable[User]]:
    """Dependency factory: the user needs `minimum` or higher (admin includes moderator)."""

    async def dependency(user: CurrentUser) -> User:
        if ROLE_RANK.get(user.role, -1) < ROLE_RANK[minimum]:
            raise AppError(403, "forbidden", "You do not have permission to do this.")
        return user

    return dependency


def user_rate_limit(name: str, rule: Rule) -> Callable[[Request, User], Awaitable[None]]:
    """Per-account write limit, applied after authentication. Complements the per-IP middleware
    limit, which has to stay generous because many mobile users share one carrier IP."""

    async def dependency(request: Request, user: CurrentUser) -> None:
        limiter: FixedWindowLimiter = request.app.state.limiter
        retry_after = limiter.hit(f"user:{user.id}:{name}", rule)
        if retry_after is not None:
            raise AppError(
                429,
                "rate_limited",
                "Too many requests. Try again later.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
