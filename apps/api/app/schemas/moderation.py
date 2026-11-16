import uuid
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator


class ModerationDecision(BaseModel):
    """A moderator's decision. Deliberately not free-form field edits: a decision can only move an
    item between the states that exist, so it can never produce an inconsistent row."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None

    @model_validator(mode="after")
    def _reject_needs_a_reason(self) -> Self:
        if not self.reason:
            self.reason = None
        if self.decision == "reject" and self.reason is None:
            raise ValueError("a reason is required when rejecting")
        return self


class SpotModerated(BaseModel):
    id: uuid.UUID
    slug: str
    status: Literal["approved", "rejected", "deleted"]


class PhotoModerated(BaseModel):
    id: uuid.UUID
    spot_id: uuid.UUID
    status: Literal["approved", "rejected"]
