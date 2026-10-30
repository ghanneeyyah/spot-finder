import asyncio
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.dependencies import DbSession
from app.middleware.error_handler import AppError

router = APIRouter(prefix="/api", tags=["health"])


class Health(BaseModel):
    status: Literal["ok"]
    database: Literal["ok"]


@router.get("/health", response_model=Health)
async def health(db: DbSession) -> Health:
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2)
    except Exception as exc:
        raise AppError(503, "database_unavailable", "The database is unavailable.") from exc
    return Health(status="ok", database="ok")
