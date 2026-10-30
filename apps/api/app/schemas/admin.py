import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ModerationItem(BaseModel):
    kind: Literal["spot", "photo"]
    id: uuid.UUID
    spot_id: uuid.UUID
    spot_name: str
    photo_url: str | None
    created_at: datetime
