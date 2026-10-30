import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

ReportedTier = Literal["green", "yellow", "red"]


class SafetyReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spot_id: uuid.UUID
    reported_tier: ReportedTier
    comment: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None

    @field_validator("comment")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        return value or None


class SafetyReportOut(BaseModel):
    """Public view of a report. Deliberately has no author fields."""

    id: uuid.UUID
    reported_tier: ReportedTier
    comment: str | None
    created_at: datetime
