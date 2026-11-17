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




def test_booking_info_rejects_javascript_urls_and_bad_whatsapp() -> None:
    # Explicitly verify Pydantic blocks XSS vectors on HttpUrl
    with pytest.raises(ValidationError):
        BookingInfo(is_bookable=True, booking_url="javascript:alert(1)")
        
    with pytest.raises(ValidationError, match="String should match pattern"):
        BookingInfo(is_bookable=True, whatsapp_contact="not-a-phone-number")
        
    with pytest.raises(ValidationError, match="String should match pattern"):
        BookingInfo(is_bookable=True, whatsapp_contact="+abc12345678")

    # Prove the happy path works
    valid = BookingInfo(
        is_bookable=True, 
        whatsapp_contact="+2348012345678", 
        booking_url="https://example.com/book"
    )
    assert valid.whatsapp_contact == "+2348012345678"
    assert str(valid.booking_url) == "https://example.com/book/"


def test_saved_spot_rejects_html_tags_but_allows_math_brackets() -> None:
    # 1. Reject Stored XSS vectors
    with pytest.raises(ValidationError, match="Notes must not contain HTML tags"):
        SavedSpotCreate(spot_id=uuid.uuid4(), notes="<script>alert(1)</script>")
        
    with pytest.raises(ValidationError, match="Notes must not contain HTML tags"):
        SavedSpotCreate(spot_id=uuid.uuid4(), notes="<b>bold note</b>")
        
    with pytest.raises(ValidationError, match="Notes must not contain HTML tags"):
        SavedSpotCreate(spot_id=uuid.uuid4(), notes="<img src='x' onerror='alert(1)'>")

    # 2. Allow harmless mathematical/directional brackets
    valid = SavedSpotCreate(spot_id=uuid.uuid4(), notes="Meet at 5 < 10 people, look for the sign -> over there")
    assert "5 < 10" in valid.notes