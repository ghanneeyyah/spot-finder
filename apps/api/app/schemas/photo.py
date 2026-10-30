import uuid
from typing import Literal

from pydantic import BaseModel


class PhotoSubmitted(BaseModel):
    id: uuid.UUID
    spot_id: uuid.UUID
    status: Literal["pending_review"] = "pending_review"
