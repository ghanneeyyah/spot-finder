import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class SubmittedSpot(BaseModel):
    """What a moderator needs to judge a submission."""

    category: str
    state: str
    city: str
    address: str | None
    description: str | None
    cost_estimate_text: str | None
    best_time: str | None
    amenities: dict[str, Any]
    latitude: float
    longitude: float


class ModerationItem(BaseModel):
    kind: Literal["spot", "photo"]
    id: uuid.UUID
    spot_id: uuid.UUID
    spot_name: str
    spot_slug: str
    # Display name, falling back to email. None only if the account has neither.
    submitter: str | None
    photo_url: str | None
    spot: SubmittedSpot | None
    created_at: datetime
