import re
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    field_validator,
)

from app.utils.geo import NG_LAT, NG_LNG

Category = Literal["nature", "food", "historical", "hangout", "beach", "park", "other"]
Tier = Literal["green", "yellow", "red", "unverified"]

NIGERIAN_STATES = (
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue", "Borno",
    "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", "FCT", "Gombe", "Imo", "Jigawa",
    "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun",
    "Ondo", "Osun", "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara",
)  # fmt: skip
_STATES_BY_LOWER = {s.lower(): s for s in NIGERIAN_STATES}
_AMENITY_KEY = re.compile(r"^[a-z][a-z0-9_]{0,29}$")

Text = Annotated[str, StringConstraints(strip_whitespace=True)]


class SpotSummary(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    category: Category
    state: str
    city: str
    latitude: float
    longitude: float
    # 'unverified' until at least one community report exists, whatever the stored tier says.
    display_tier: Tier
    safety_report_count: int


class SpotNearby(SpotSummary):
    distance_m: float


class PhotoOut(BaseModel):
    id: uuid.UUID
    url: str


class SpotDetail(SpotSummary):
    safety_tier: Tier
    safety_score: float | None
    description: str | None
    address: str | None
    cost_estimate_text: str | None
    best_time: str | None
    amenities: dict[str, Any]
    is_verified: bool
    photos: list[PhotoOut]
    created_at: datetime
    updated_at: datetime


class SpotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[Text, StringConstraints(min_length=2, max_length=120)]
    description: Annotated[Text, StringConstraints(max_length=2000)] | None = None
    category: Category
    state: str
    city: Annotated[Text, StringConstraints(min_length=1, max_length=80)]
    address: Annotated[Text, StringConstraints(max_length=200)] | None = None
    latitude: float = Field(ge=NG_LAT[0], le=NG_LAT[1])
    longitude: float = Field(ge=NG_LNG[0], le=NG_LNG[1])
    cost_estimate_text: Annotated[Text, StringConstraints(max_length=200)] | None = None
    best_time: Annotated[Text, StringConstraints(max_length=120)] | None = None
    amenities: dict[str, StrictBool] = Field(default_factory=dict, max_length=20)

    @field_validator("state")
    @classmethod
    def _state(cls, value: str) -> str:
        canonical = _STATES_BY_LOWER.get(value.strip().lower())
        if canonical is None:
            raise ValueError("must be a Nigerian state name or FCT")
        return canonical

    @field_validator("description", "address", "cost_estimate_text", "best_time")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("amenities")
    @classmethod
    def _amenity_keys(cls, value: dict[str, StrictBool]) -> dict[str, StrictBool]:
        if any(not _AMENITY_KEY.match(key) for key in value):
            raise ValueError("amenity keys must be lowercase snake_case, up to 30 characters")
        return value


class SpotSubmitted(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    status: Literal["pending_review"] = "pending_review"
