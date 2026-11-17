import uuid
import pytest
from pydantic import ValidationError
from app.schemas.spot import BookingInfo
from app.schemas.itinerary import SavedSpotCreate

def test_booking_info_requires_contact_when_bookable() -> None:
    # Valid: not bookable, no links
    BookingInfo(is_bookable=False)
    
    # Valid: bookable with URL
    BookingInfo(is_bookable=True, booking_url="https://vendor.com/book")
    
    # Valid: bookable with WhatsApp
    BookingInfo(is_bookable=True, whatsapp_contact="+2348000000000")
    
    # Invalid: bookable but no contact method
    with pytest.raises(ValidationError, match="Bookable spots require a booking_url or whatsapp_contact"):
        BookingInfo(is_bookable=True)

def test_booking_info_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        BookingInfo(is_bookable=False, malicious_injection="hacked")

def test_saved_spot_create_rejects_user_id() -> None:
    # Valid: only the allowed fields
    SavedSpotCreate(spot_id=uuid.uuid4(), notes="Looking forward to this!")
    
    # Invalid: attempting an IDOR attack by passing a user_id in the payload
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SavedSpotCreate(spot_id=uuid.uuid4(), user_id=uuid.uuid4())