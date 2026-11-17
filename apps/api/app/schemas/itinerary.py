import re
import uuid
from datetime import date, datetime
from typing import Annotated
from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app.schemas.spot import SpotSummary

Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
_HTML_TAG = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")


class SavedSpotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    spot_id: uuid.UUID
    planned_date: date | None = None
    notes: Text | None = None

    @field_validator("notes")
    @classmethod
    def reject_html(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if _HTML_TAG.search(v):
            raise ValueError("Notes must not contain HTML tags")
        return v


class SavedSpotUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    planned_date: date | None = None
    notes: Text | None = None

    @field_validator("notes")
    @classmethod
    def reject_html(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if _HTML_TAG.search(v):
            raise ValueError("Notes must not contain HTML tags")
        return v

# ... SavedSpotOut remains unchanged

class SavedSpotOut(BaseModel):
    """Output for a scheduled spot, nested with the SpotSummary for rich UI rendering."""
    spot_id: uuid.UUID
    planned_date: date | None
    notes: str | None
    saved_at: datetime
    
    # We embed the summary so the frontend can render the "poster" feed of saved itineraries
    spot: SpotSummary

    model_config = ConfigDict(from_attributes=True)