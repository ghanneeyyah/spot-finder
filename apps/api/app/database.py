from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base shared by every model. Engine and session live here from deliverable 4."""


def normalize_database_url(url: str) -> str:
    """Force the asyncpg driver; Railway and most hosts hand out plain postgresql:// URLs."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix) :]
    return url
