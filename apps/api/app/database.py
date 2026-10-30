from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

if TYPE_CHECKING:
    from app.config import Settings


class Base(DeclarativeBase):
    """Declarative base shared by every model."""


def normalize_database_url(url: str) -> str:
    """Force the asyncpg driver; Railway and most hosts hand out plain postgresql:// URLs."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix) :]
    return url


def build_engine(settings: "Settings") -> AsyncEngine:
    """One engine per process. Pool sizing is per worker process: with N workers the totals are
    N x pool_size connections plus N x max_overflow burst connections."""
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"server_settings": {"statement_timeout": "15000"}},
    )


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
