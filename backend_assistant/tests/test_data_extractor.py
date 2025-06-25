import pytest
import asyncio # For async test functions
import aiohttp # For mocking session
from unittest.mock import MagicMock, AsyncMock

from backend_assistant.app.data_extractor import DataExtractor
from backend_assistant.app.config import Settings

# Minimal mock settings for tests
@pytest.fixture
def mock_settings(monkeypatch):
    settings_attrs = {
        "CLIENT_BILLING_RATES_PATH": "non_existent_rates.json", # Test file not found path
        "GEOCODING_API_URL": "https://nominatim.openstreetmap.org/search",
        "GEOCODING_USER_AGENT": "pytest_test_agent/1.0",
        "SQLITE_DB_PATH": ":memory:", # Use in-memory SQLite for tests
        # Add other necessary settings if DataExtractor directly uses them
    }
    for attr, value in settings_attrs.items():
        monkeypatch.setattr(f"backend_assistant.app.config.settings.{attr}", value, raising=False)

    # Reload settings if they are module-level singletons and already loaded
    # This is a bit tricky. For Pydantic settings, usually they are loaded once.
    # A better way might be to allow settings injection or have DataExtractor take settings obj.
    # For now, assume direct use of global 'settings' from config.py is what we test.


@pytest.fixture
async def mock_aiohttp_session():
    session = AsyncMock(spec=aiohttp.ClientSession)
    # You can configure mock responses further if needed for specific tests
    # e.g., session.get.return_value.__aenter__.return_value.json.return_value = {"mock_key": "mock_value"}
    return session


@pytest.mark.asyncio
async def test_data_extractor_initialization(mock_settings, mock_aiohttp_session):
    """Test basic initialization of DataExtractor."""
    try:
        extractor = DataExtractor(session=mock_aiohttp_session)
        assert extractor is not None
        assert extractor.client_billing_rates == {} # Expect empty if file not found
    except Exception as e:
        pytest.fail(f"DataExtractor initialization failed: {e}")


def test_is_authorization_email_keyword_in_subject(mock_settings, event_loop, mock_aiohttp_session): # event_loop for session if needed by constructor
    """Test if keyword in subject correctly identifies an auth email."""
    # Need to run async constructor if DataExtractor had async init
    # For now, assuming sync constructor for DataExtractor
    extractor = DataExtractor(session=mock_aiohttp_session) # Session mock not used here but required by constructor

    email_content_auth = {
        "subject": "Work Authorization - Project X",
        "body_text": "Please find details attached."
    }
    assert extractor.is_authorization_email(email_content_auth) is True

    email_content_auth_id = {
        "subject": "Update on your Service ID: ABC123",
        "body_text": "Details regarding your service."
    }
    assert extractor.is_authorization_email(email_content_auth_id) is True

    email_content_no_auth = {
        "subject": "Project Update",
        "body_text": "Regular update, no authorization here."
    }
    assert extractor.is_authorization_email(email_content_no_auth) is False


def test_is_authorization_email_keyword_in_body(mock_settings, mock_aiohttp_session):
    extractor = DataExtractor(session=mock_aiohttp_session)
    email_content_auth = {
        "subject": "Project Alpha",
        "body_text": "Details for Authorization ID No. XYZ789 confirm the work."
    }
    assert extractor.is_authorization_email(email_content_auth) is True


def test_extract_authorization_id(mock_settings, mock_aiohttp_session):
    extractor = DataExtractor(session=mock_aiohttp_session)
    text_1 = "Authorization ID No.: ABC-123-DEF"
    assert extractor.extract_authorization_id(text_1) == "ABC-123-DEF"

    text_2 = "Please refer to Auth ID: XYZ987 for this task."
    assert extractor.extract_authorization_id(text_2) == "XYZ987"

    text_3 = "Service ID: S-001-A"
    assert extractor.extract_authorization_id(text_3) == "S-001-A"

    text_no_id = "This email contains no specific authorization identifier."
    assert extractor.extract_authorization_id(text_no_id) is None


def test_extract_mileage(mock_settings, mock_aiohttp_session):
    extractor = DataExtractor(session=mock_aiohttp_session)
    text_1 = "Travel involved 25.5 miles for this trip."
    assert extractor.extract_mileage(text_1) == 25.5

    text_2 = "Mileage: 100 mi"
    assert extractor.extract_mileage(text_2) == 100.0

    text_3 = "No explicit mileage mentioned."
    assert extractor.extract_mileage(text_3) is None

# TODO: Add tests for _parse_date_time (would need more robust examples and mocking for pytz if complex)
# TODO: Add tests for geocode_address (would need to mock aiohttp session responses carefully)
# TODO: Add tests for process_email_content (more comprehensive integration test within the class)

# Example of how a geocoding test might look (needs more setup for DB cache part)
# @pytest.mark.asyncio
# async def test_geocode_address_success(mock_settings, mock_aiohttp_session):
#     # Configure mock_aiohttp_session to return a valid Nominatim-like response
#     mock_response_data = [{"lat": "34.0522", "lon": "-118.2437", "display_name": "Los Angeles"}]
#     mock_aiohttp_session.get.return_value.__aenter__.return_value.json.return_value = mock_response_data
#     mock_aiohttp_session.get.return_value.__aenter__.return_value.status = 200
#     mock_aiohttp_session.get.return_value.__aenter__.return_value.raise_for_status = MagicMock()

#     # Mock database for caching (this part needs a proper DB mock or temp DB solution)
#     # For now, assume caching is tested separately or this test focuses on API call part.

#     extractor = DataExtractor(session=mock_aiohttp_session)
#     address_to_geocode = "Los Angeles, CA"
#     result = await extractor.geocode_address(address_to_geocode)

#     assert result is not None
#     assert result["latitude"] == 34.0522
#     assert result["longitude"] == -118.2437
#     mock_aiohttp_session.get.assert_called_once() # Check if API was called (assuming cache miss)
```
