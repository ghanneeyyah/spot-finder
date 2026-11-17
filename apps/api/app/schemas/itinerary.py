import uuid
from datetime import date, datetime
from typing import Annotated
from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.spot import SpotSummary

Text = Annotated[str, StringConstraints(strip_whitespace=True)]


class SavedSpotCreate(BaseModel):
    """Payload for saving a spot to the user's itinerary."""
    model_config = ConfigDict(extra="forbid")
    
    spot_id: uuid.UUID
    planned_date: date | None = None
    notes: Annotated[Text, StringConstraints(max_length=1000)] | None = None


class SavedSpotUpdate(BaseModel):
    """Payload for updating an existing itinerary entry."""
    model_config = ConfigDict(extra="forbid")
    
    planned_date: date | None = None
    notes: Annotated[Text, StringConstraints(max_length=1000)] | None = None


class SavedSpotOut(BaseModel):
    """Output for a scheduled spot, nested with the SpotSummary for rich UI rendering."""
    spot_id: uuid.UUID
    planned_date: date | None
    notes: str | None
    saved_at: datetime
    
    # We embed the summary so the frontend can render the "poster" feed of saved itineraries
    spot: SpotSummary

    model_config = ConfigDict(from_attributes=True)