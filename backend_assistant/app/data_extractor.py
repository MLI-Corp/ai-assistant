import logging
import json
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
import unittest.mock # For mocking session in test

import pytz # For timezone conversion
import aiohttp # For async HTTP requests (geocoding)

from .config import settings
from .database import get_db_connection, log_event

logger = logging.getLogger(__name__)

# Basic keyword to identify relevant emails
AUTHORIZATION_KEYWORDS = ["Authorization ID No.", "Work Authorization", "Service Authorization"]
# Regex to find Authorization ID (example, needs refinement)
AUTH_ID_REGEX = r"(?:Authorization ID No\.|Auth ID|Authorization #|Service ID):\s*([A-Z0-9-]+)"
# Regex for dates (examples, will need robust parsing)
DATE_REGEX_DMY = r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b" # DD/MM/YYYY or DD.MM.YY etc.
DATE_REGEX_MDY = r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b" # MM/DD/YYYY
DATE_REGEX_YMD = r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b" # YYYY/MM/DD
TIME_REGEX = r"\b(\d{1,2}):(\d{2})\s*(AM|PM)?\b"
MILEAGE_REGEX = r"(\d+\.?\d*)\s*(miles|mi)\b"

CST_TIMEZONE = pytz.timezone('America/Chicago')

class DataExtractor:
    def __init__(self, session: aiohttp.ClientSession):
        self.client_billing_rates = self._load_client_billing_rates()
        self.session = session # Use shared session

    def _load_client_billing_rates(self) -> Dict:
        """Loads client-specific billing rates from a JSON file."""
        rates_path = settings.CLIENT_BILLING_RATES_PATH
        try:
            with open(rates_path, 'r') as f:
                rates = json.load(f)
                logger.info(f"Successfully loaded client billing rates from {rates_path}")
                return rates
        except FileNotFoundError:
            logger.warning(f"Client billing rates file not found at {rates_path}. No rates loaded.")
            log_event("CONFIG_ERROR", f"Billing rates file not found: {rates_path}")
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from client billing rates file: {rates_path}")
            log_event("CONFIG_ERROR", f"Billing rates JSON error in: {rates_path}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading billing rates: {e}")
            log_event("CONFIG_ERROR", f"Unexpected error loading billing rates: {e}")
        return {}

    def get_client_rate(self, client_identifier: str, rate_type: str) -> Optional[float]:
        """
        Retrieves a specific rate for a client.
        Client identifier could be email domain, full email, or a name.
        Rate type could be 'mileage_rate', 'hourly_rate', etc.
        """
        # Simplistic lookup: exact match on client_identifier.
        # Could be made more sophisticated (e.g., domain matching).
        client_config = self.client_billing_rates.get(client_identifier)
        if client_config:
            return client_config.get(rate_type)

        # Fallback to a default rate if any
        default_config = self.client_billing_rates.get("default")
        if default_config:
            return default_config.get(rate_type)
        return None

    def _parse_date_time(self, text_content: str) -> Optional[datetime]:
        """Attempts to parse date and time from text and convert to CST datetime."""
        # This is a very basic parser and would need significant improvement for production.
        # Consider using libraries like `dateutil.parser` or `pendulum` for robust parsing.

        date_match = None
        # Try common date formats (this order might matter or need adjustment)
        for regex in [DATE_REGEX_MDY, DATE_REGEX_DMY, DATE_REGEX_YMD]: # Prioritize M/D/Y for US context
            m = re.search(regex, text_content)
            if m:
                parts = m.groups()
                try:
                    if regex == DATE_REGEX_MDY: # MM/DD/YYYY
                        dt = datetime(int(parts[2]), int(parts[0]), int(parts[1]))
                    elif regex == DATE_REGEX_DMY: # DD/MM/YYYY
                        dt = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
                    elif regex == DATE_REGEX_YMD: # YYYY/MM/DD
                        dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                    else: # Should not happen
                        continue
                    date_match = dt
                    break
                except ValueError:
                    logger.debug(f"Date regex {regex} matched '{m.group(0)}' but was not a valid date.")
                    continue

        if not date_match:
            logger.debug("No date found in email content.")
            return None

        time_match_obj = re.search(TIME_REGEX, text_content)
        hour, minute = 0, 0
        if time_match_obj:
            h, m, ampm = time_match_obj.groups()
            hour = int(h)
            minute = int(m)
            if ampm and ampm.lower() == 'pm' and hour < 12:
                hour += 12
            elif ampm and ampm.lower() == 'am' and hour == 12: # Midnight case
                hour = 0
        else: # Default to midnight if no time found but date was
            logger.debug("No time found, defaulting to 00:00 for the matched date.")

        try:
            # Combine date and time
            final_dt_naive = date_match.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # Assume the parsed date/time is local to where email was sent (often not specified)
            # For this system, let's assume it's US-based, often EST or PST.
            # A better approach might be to try and infer timezone or have a default configurable one.
            # For now, we'll treat it as naive and then localize to CST.
            # If the time is truly "floating", this might be okay.
            # If it has a specific source TZ, that needs to be handled.

            # Localize to CST - this assumes the naive datetime is *already* in CST conceptually,
            # or that we are interpreting a floating time as CST.
            # If the source time is known to be, say, UTC, then:
            # final_dt_utc = pytz.utc.localize(final_dt_naive)
            # final_dt_cst = final_dt_utc.astimezone(CST_TIMEZONE)
            # For now, directly localizing as if it's intended for CST:
            final_dt_cst = CST_TIMEZONE.localize(final_dt_naive)
            return final_dt_cst
        except pytz.exceptions.AmbiguousTimeError:
            logger.warning(f"Ambiguous time for {final_dt_naive} in CST (e.g. DST fallback). Defaulting to standard time.")
            final_dt_cst = CST_TIMEZONE.localize(final_dt_naive, is_dst=False) # Or True, or handle differently
            return final_dt_cst
        except pytz.exceptions.NonExistentTimeError:
            logger.warning(f"Non-existent time for {final_dt_naive} in CST (e.g. DST spring forward).")
            # This requires more sophisticated handling, e.g., moving to next valid time.
            return None # Or raise error
        except Exception as e:
            logger.error(f"Error creating or localizing datetime: {e}")
            return None


    async def _get_cached_geocode(self, address: str) -> Optional[Dict[str, Any]]:
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT latitude, longitude, full_response FROM geocoding_cache WHERE query_address = ?", (address,))
            row = cursor.fetchone()
            if row:
                logger.info(f"Geocoding cache hit for address: {address}")
                log_event("GEOCODE_CACHE_HIT", f"Cache hit for: {address}")
                return {"latitude": row["latitude"], "longitude": row["longitude"], "full_response": json.loads(row["full_response"])}
            return None
        except sqlite3.Error as e:
            logger.error(f"SQLite error fetching geocode cache: {e}")
            return None
        finally:
            if conn:
                conn.close()

    async def _cache_geocode_result(self, address: str, lat: float, lon: float, full_response: Dict):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO geocoding_cache (query_address, latitude, longitude, full_response) VALUES (?, ?, ?, ?)",
                (address, lat, lon, json.dumps(full_response))
            )
            conn.commit()
            logger.info(f"Cached geocoding result for: {address}")
        except sqlite3.Error as e:
            logger.error(f"SQLite error caching geocode: {e}")
            log_event("GEOCODE_CACHE_FAIL", f"Failed to cache geocode for {address}: {e}")
        finally:
            if conn:
                conn.close()

    async def geocode_address(self, address: str, client_address: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Geocodes a single address or calculates mileage between two if client_address is provided.
        Returns a dict with 'latitude', 'longitude' for a single address,
        or 'mileage' if two addresses are provided.
        Uses Nominatim. Respect their usage policy (max 1 req/sec, User-Agent).
        """
        cached_result = await self._get_cached_geocode(address)
        if cached_result:
            # If we need mileage, we'd need to geocode client_address too
            # For now, this simplified version just returns coords for the primary address
            return {"latitude": cached_result["latitude"], "longitude": cached_result["longitude"]}

        # Use the session passed during initialization
        params = {'q': address, 'format': 'json', 'limit': 1, 'polygon_geojson': 1} # polygon_geojson for more details if needed
from .utils import retry_async # Import the retry decorator

        # TODO: Add country/city biasing if appropriate from settings

        @retry_async(attempts=2, delay_seconds=3) # Fewer attempts for geocoding to avoid hammering public API
        async def _do_geocode():
            logger.info(f"Geocoding address: {address} using {settings.GEOCODING_API_URL}")
            log_event("GEOCODING_API_CALL", f"Geocoding: {address}")
            async with self.session.get(settings.GEOCODING_API_URL, params=params, headers={"User-Agent": settings.GEOCODING_USER_AGENT}) as response:
                response.raise_for_status()
                return await response.json()

        try:
            results = await _do_geocode()
                if results:
                    location = results[0]
                    lat = float(location['lat'])
                    lon = float(location['lon'])
                    await self._cache_geocode_result(address, lat, lon, location)

                    # TODO: Implement mileage calculation if client_address is also provided.
                    # This would involve another geocoding call for client_address (or cache lookup)
                    # and then using a Haversine formula or similar.
                    # For now, just returns the geocoded primary address.
                    return {"latitude": lat, "longitude": lon, "display_name": location.get("display_name")}
                else:
                    logger.warning(f"No geocoding results found for address: {address}")
                    log_event("GEOCODING_NO_RESULTS", f"No results for: {address}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"aiohttp client error during geocoding for {address}: {e}")
            log_event("GEOCODING_HTTP_ERROR", f"HTTP error for {address}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during geocoding for {address}: {e}", exc_info=True)
            log_event("GEOCODING_UNEXPECTED_ERROR", f"Unexpected error for {address}: {e}")
            return None


    def is_authorization_email(self, email_content: Dict[str, Any]) -> bool:
        """Determines if an email is a work authorization email."""
        subject = email_content.get("subject", "").lower()
        body = email_content.get("body_text", "").lower() # Use text body for keyword search

        for keyword in AUTHORIZATION_KEYWORDS:
            if keyword.lower() in subject or keyword.lower() in body:
                logger.info(f"Email subject/body contains authorization keyword: '{keyword}'")
                return True
        # Also check for Auth ID regex in body as a fallback
        if re.search(AUTH_ID_REGEX, email_content.get("body_text", ""), re.IGNORECASE):
            logger.info("Email body contains Authorization ID pattern.")
            return True

        logger.debug(f"Email (Subject: {subject[:50]}...) not identified as authorization email.")
        return False

    def extract_authorization_id(self, text_content: str) -> Optional[str]:
        match = re.search(AUTH_ID_REGEX, text_content, re.IGNORECASE)
        if match:
            auth_id = match.group(1).strip()
            logger.info(f"Extracted Authorization ID: {auth_id}")
            return auth_id
        logger.debug("No Authorization ID pattern found in text.")
        return None

    def extract_mileage(self, text_content: str) -> Optional[float]:
        match = re.search(MILEAGE_REGEX, text_content, re.IGNORECASE)
        if match:
            try:
                mileage = float(match.group(1))
                logger.info(f"Extracted mileage: {mileage}")
                return mileage
            except ValueError:
                logger.warning(f"Could not parse mileage from regex match: {match.group(1)}")
        return None

    def extract_client_info(self, email_from_header: str) -> Dict[str, str]:
        """
        Extracts client name and email from the 'From' header.
        Example 'From' header: "John Doe <john.doe@example.com>"
        """
        name_match = re.match(r"(.+)<(.+)>", email_from_header)
        if name_match:
            name = name_match.group(1).strip().replace('"', '')
            email = name_match.group(2).strip()
        else: # Just an email address, or unparseable
            name = email_from_header.split('@')[0] # Fallback: use part before @ as name
            email = email_from_header.strip()
        return {"name": name, "email": email}


    async def process_email_content(self, email_content: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processes the parsed email content to extract structured data.
        Returns a dictionary with extracted data or None if not relevant.
        """
        if not self.is_authorization_email(email_content):
            logger.info(f"Email (Subject: {email_content.get('subject','N/A')[:30]}...) is not an authorization type.")
            return None

        logger.info(f"Processing potential authorization email: Subject='{email_content.get('subject','N/A')}'")

        # Use text body primarily, can fallback to HTML if text is empty or lacks info
        # For now, focusing on text_body. HTML parsing can be complex (e.g. using BeautifulSoup)
        body = email_content.get("body_text", "")
        if not body and email_content.get("body_html"):
            # Basic HTML to text conversion (very naive, consider library for better results)
            # body = re.sub(r'<[^>]+>', '', email_content.get("body_html",""))
            logger.info("Using HTML body as text body is empty. Note: HTML parsing not fully implemented.")
            body = "HTML Body - Content needs proper parsing." # Placeholder

        auth_id = self.extract_authorization_id(body)
        if not auth_id: # If not found in body, try subject
            auth_id = self.extract_authorization_id(email_content.get("subject", ""))

        if not auth_id:
            logger.warning("Could not extract Authorization ID. Skipping email.")
            log_event("DATA_EXTRACTION_FAIL", "Missing Authorization ID", f"Subject: {email_content.get('subject','N/A')}")
            return None

        service_datetime_cst = self._parse_date_time(body)
        mileage = self.extract_mileage(body)

        client_info = self.extract_client_info(email_content.get("from", ""))

        # Placeholder for patient and location - these often require more complex NLP or specific formats
        patient_name: Optional[str] = None # TODO: Extract patient name
        service_location_address: Optional[str] = None # TODO: Extract service location address

        # Try to extract patient name (very naive example)
        patient_match = re.search(r"(?:Patient|Client Name):\s*(.+)", body, re.IGNORECASE)
        if patient_match:
            patient_name = patient_match.group(1).splitlines()[0].strip()
            logger.info(f"Extracted Patient Name: {patient_name}")

        # Try to extract service location (very naive example)
        location_match = re.search(r"(?:Location|Address|Service Address):\s*(.+)", body, re.IGNORECASE)
        if location_match:
            service_location_address = location_match.group(1).splitlines()[0].strip()
            logger.info(f"Extracted Service Location: {service_location_address}")


        # Geocode service location if address found and mileage not explicitly provided
        # For now, this only geocodes the service_location_address
        # Mileage calculation would require a second address (client's or office)
        geocoded_location_info = None
        if service_location_address:
            geocoded_location_info = await self.geocode_address(service_location_address)
            if geocoded_location_info:
                logger.info(f"Geocoded service location '{service_location_address}': {geocoded_location_info}")
            else:
                logger.warning(f"Failed to geocode service location: {service_location_address}")


        extracted_data = {
            "authorization_id": auth_id,
            "client_name": client_info["name"],
            "client_email": client_info["email"],
            "service_date_cst_iso": service_datetime_cst.isoformat() if service_datetime_cst else None,
            "service_datetime_obj_cst": service_datetime_cst, # Keep datetime object for calendar
            "mileage_extracted": mileage,
            "mileage_calculated": None, # Placeholder for calculated mileage
            "patient_name": patient_name,
            "service_location_address": service_location_address,
            "geocoded_service_location": geocoded_location_info,
            "original_email_subject": email_content.get("subject"),
            "original_email_body_preview": body[:200] + "..." if body else "",
            "original_email_uid": email_content.get("uid") # Important for archiving
        }

        # TODO: If mileage is None and service_location_address and client_address (from config?) exist,
        # then calculate mileage using geocoded coordinates.

        log_event("DATA_EXTRACTION_SUCCESS", f"Extracted data for Auth ID: {auth_id}", json.dumps({k:v for k,v in extracted_data.items() if k != "service_datetime_obj_cst"}, indent=2))
        logger.info(f"Successfully extracted data for Auth ID {auth_id}: {extracted_data}")
        return extracted_data

# Example Usage (for direct testing if needed)
async def test_data_extraction():
    logging.basicConfig(level=logging.INFO)
    # Mock settings for testing if .env isn't loaded the same way
    class MockSettings:
        CLIENT_BILLING_RATES_PATH = "mock_billing_rates.json"
        GEOCODING_API_URL = "https_nominatim.openstreetmap.org/search" # Add schema for aiohttp
        GEOCODING_USER_AGENT = "TestAgent/1.0"
        SQLITE_DB_PATH = "test_assistant.db" # Use a test DB

    global settings # careful with global modification in tests
    # settings = MockSettings() # Uncomment and adjust if direct testing without full app context

    # Create mock billing rates file
    # with open(MockSettings.CLIENT_BILLING_RATES_PATH, 'w') as f:
    #    json.dump({"default": {"mileage_rate": 0.55}}, f)

    # Initialize DB for logging and caching
    from .database import initialize_db
    try:
        initialize_db() # Will use settings.SQLITE_DB_PATH
    except Exception as e:
        print(f"DB init failed for test: {e}")
        # return

    # For testing DataExtractor, it now needs a session
    async def mock_session_get(*args, **kwargs): # Basic mock
        class MockResponse:
            def __init__(self, json_data, status_code):
                self.json_data = json_data
                self.status = status_code
            async def json(self): return self.json_data
            async def text(self): return json.dumps(self.json_data)
            def raise_for_status(self): pass
            async def __aenter__(self): return self
            async def __aexit__(self, exc_type, exc, tb): pass

        # Simulate Nominatim response structure for geocoding
        if settings.GEOCODING_API_URL in args[0] or settings.GEOCODING_API_URL in kwargs.get('url',''):
            return MockResponse([{"lat": "0.0", "lon": "0.0", "display_name": "Mock Address"}], 200)
        return MockResponse({}, 404) # Default mock response

    mock_aiohttp_session = unittest.mock.AsyncMock(spec=aiohttp.ClientSession)
    mock_aiohttp_session.get = mock_session_get # simplistic mock for get

    extractor = DataExtractor(session=mock_aiohttp_session)

    sample_email_body_1 = """
    Subject: Work Authorization - ID ABC12345
    Dear Team,
    Please find attached the work authorization for services.
    Authorization ID No.: ABC12345
    Service Date: 07/15/2024
    Service Time: 2:30 PM
    Patient Name: John Doe
    Location: 123 Main St, Anytown, USA
    Mileage: 25.5 miles
    Thank you.
    """
    sample_email_content_1 = {
        "subject": "Work Authorization - ID ABC12345",
        "from": "Client Services <client@example.com>",
        "body_text": sample_email_body_1,
        "uid": "testuid123"
    }

    extracted = await extractor.process_email_content(sample_email_content_1)
    if extracted:
        print("\n--- Extracted Data (Sample 1) ---")
        for key, val in extracted.items():
            print(f"  {key}: {val}")
    else:
        print("\n--- No data extracted (Sample 1) ---")

    sample_email_body_2 = """
    Subject: Service Request Approved
    Hi,
    Your request for service (Auth ID: XYZ-987) on 20.08.2024 at 09:00 is approved.
    Client: Jane Smith
    Address: 456 Oak Ave, Otherville, CA
    No mileage specified.
    """
    sample_email_content_2 = {
        "subject": "Service Request Approved",
        "from": "approvals@company.com",
        "body_text": sample_email_body_2,
        "uid": "testuid456"
    }
    extracted_2 = await extractor.process_email_content(sample_email_content_2)
    if extracted_2:
        print("\n--- Extracted Data (Sample 2) ---")
        for key, val in extracted_2.items():
            print(f"  {key}: {val}")
    else:
        print("\n--- No data extracted (Sample 2) ---")

    await extractor.close_http_session() # Important for aiohttp

if __name__ == "__main__":
    # To run this test:
    # Ensure .env.assistant is configured or mock settings above.
    # python -m backend_assistant.app.data_extractor from project root
    asyncio.run(test_data_extraction())
