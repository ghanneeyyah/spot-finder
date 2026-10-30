from typing import Any

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int
