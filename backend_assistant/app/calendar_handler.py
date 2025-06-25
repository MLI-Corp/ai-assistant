import logging
import datetime # Standard datetime
from typing import Optional, Dict, Any

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

from .config import settings
from .database import log_event

logger = logging.getLogger(__name__)

# Define the scopes needed. For creating events, this is usually sufficient.
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

class GoogleCalendarHandler:
    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.refresh_token = settings.GOOGLE_REFRESH_TOKEN
        self.calendar_id = settings.GOOGLE_CALENDAR_ID
        self.creds: Optional[Credentials] = None
        self.service: Optional[Resource] = None

    def _get_credentials(self) -> Optional[Credentials]:
        """
        Gets valid Google API credentials.
        Uses the stored refresh token to get an access token.
        """
        if not all([self.client_id, self.client_secret, self.refresh_token]):
            logger.warning("Google Calendar API credentials (client_id, client_secret, refresh_token) are not fully configured. Calendar integration will be disabled.")
            log_event("CALENDAR_CONFIG_MISSING", "Google Calendar credentials missing.")
            return None

        creds = Credentials(
            None, # No access token initially
            refresh_token=self.refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=SCOPES
        )

        try:
            # Check if credentials are valid and refresh if necessary
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    logger.info("Google API credentials expired. Refreshing...")
                    creds.refresh(GoogleAuthRequest())
                    logger.info("Google API credentials refreshed successfully.")
                    # Persist the (potentially updated) refresh token?
                    # Google's library usually handles this if the refresh token itself changes,
                    # but good to be aware. For simple refresh token usage, it doesn't usually change.
                    # If it did, settings.GOOGLE_REFRESH_TOKEN would need updating.
                    log_event("CALENDAR_TOKEN_REFRESHED", "Access token refreshed.")
                else:
                    # This case should ideally not be hit if refresh_token is valid,
                    # as creds.valid would be true or creds.expired would trigger refresh.
                    # If refresh_token is invalid, creds.refresh() will fail.
                    logger.error("Google API credentials are not valid and no valid refresh token is available or refresh failed.")
                    log_event("CALENDAR_INVALID_CREDS", "Invalid credentials and refresh failed or not possible.")
                    return None

            self.creds = creds
            return self.creds

        except Exception as e:
            logger.error(f"Error refreshing Google API credentials: {e}", exc_info=True)
            log_event("CALENDAR_REFRESH_ERROR", f"Error refreshing credentials: {e}")
            return None

    async def _get_service(self) -> Optional[Resource]:
        """Initializes and returns the Google Calendar API service client."""
        if not self._get_credentials(): # This ensures creds are valid and refreshed if needed
            return None

        if self.service is None: # Build service only if not already built with valid creds
            try:
                # Using an async HTTP client with google-api-python-client is complex.
                # The library is primarily synchronous. For this iteration, I'll use it synchronously.
                # For a fully async app, one might use aiohttp directly with Google's REST API
                # or run Google API calls in a thread pool executor.
                # For now, this will be a blocking call within an async app.
                # This is a known limitation/complexity when mixing sync Google libs with asyncio.
                # Consider `asyncio.to_thread` for these calls in a real async app.
                self.service = build('calendar', 'v3', credentials=self.creds, static_discovery=False)
                logger.info("Google Calendar API service client initialized.")
            except Exception as e:
                logger.error(f"Failed to build Google Calendar API service: {e}", exc_info=True)
                log_event("CALENDAR_SERVICE_FAIL", f"Failed to build calendar service: {e}")
                return None
        return self.service

    async def create_event(self, extracted_data: Dict[str, Any]) -> Optional[str]:
        """
        Creates an event in Google Calendar.
        `extracted_data` should contain `service_datetime_obj_cst` (a timezone-aware datetime object),
        `authorization_id`, `patient_name` (optional), `service_location_address` (optional).
        Returns the event ID if successful, else None.
        """
        service = await self._get_service()
        if not service:
            logger.error("Google Calendar service not available. Cannot create event.")
            return None

        service_dt_cst = extracted_data.get("service_datetime_obj_cst")
        if not service_dt_cst or not isinstance(service_dt_cst, datetime.datetime):
            logger.warning("Service date/time object not found or invalid in extracted_data. Cannot create calendar event.")
            log_event("CALENDAR_CREATE_SKIP", "Missing or invalid service datetime", f"Data: {extracted_data.get('authorization_id')}")
            return None

        # Check if service date is in the past
        # Ensure current time is also timezone-aware for comparison
        now_cst = datetime.datetime.now(pytz.timezone('America/Chicago'))
        if service_dt_cst < now_cst:
            logger.info(f"Service date {service_dt_cst.isoformat()} is in the past. Skipping calendar event creation.")
            log_event("CALENDAR_CREATE_SKIP_PAST", f"Service date {service_dt_cst.isoformat()} is past", f"AuthID: {extracted_data.get('authorization_id')}")
            return None # Successfully skipped, not an error

        # Assume event duration is 1 hour for now. This could be configurable.
        end_dt_cst = service_dt_cst + datetime.timedelta(hours=1)

        event_summary = f"Auth ID: {extracted_data.get('authorization_id', 'N/A')}"
        if extracted_data.get("patient_name"):
            event_summary += f" - Patient: {extracted_data.get('patient_name')}"

        event_location = extracted_data.get("service_location_address", "")
        if not event_location and extracted_data.get("geocoded_service_location"):
            event_location = extracted_data.get("geocoded_service_location", {}).get("display_name", "")


        event_body = {
            'summary': event_summary,
            'location': event_location,
            'description': f"Automated entry for Authorization ID: {extracted_data.get('authorization_id')}\nClient: {extracted_data.get('client_name', 'N/A')} ({extracted_data.get('client_email', 'N/A')})\nRaw email subject: {extracted_data.get('original_email_subject', 'N/A')}",
            'start': {
                'dateTime': service_dt_cst.isoformat(), # Requires ISO format string
                'timeZone': str(service_dt_cst.tzinfo), # e.g., 'America/Chicago'
            },
            'end': {
                'dateTime': end_dt_cst.isoformat(),
                'timeZone': str(end_dt_cst.tzinfo),
            },
            # 'attendees': [
            #     {'email': 'user@example.com'}, # Optional: if you want to invite someone
            # ],
            'reminders': { # Optional: default reminders
                'useDefault': True,
            },
            # Add custom properties if needed, e.g. for linking back to Auth ID
            # 'extendedProperties': {
            #     'private': { # or 'shared'
            #         'authorizationId': extracted_data.get('authorization_id')
            #     }
            # }
        }

        try:
            logger.info(f"Creating Google Calendar event: {event_summary} at {service_dt_cst.isoformat()}")
            # Note: this is a synchronous (blocking) call.
            # In a fully async app, wrap this with asyncio.to_thread:
            # created_event = await asyncio.to_thread(
            #     service.events().insert(calendarId=self.calendar_id, body=event_body).execute
            # )
            created_event = service.events().insert(calendarId=self.calendar_id, body=event_body).execute()

            event_id = created_event.get('id')
            event_html_link = created_event.get('htmlLink')
            logger.info(f"Google Calendar event created successfully. ID: {event_id}, Link: {event_html_link}")
            log_event("CALENDAR_EVENT_CREATED", f"Event '{event_summary}' created. ID: {event_id}", f"Link: {event_html_link}")
            return event_id
        except HttpError as error:
            logger.error(f"An API error occurred creating Google Calendar event: {error.resp.status} - {error._get_reason()}", exc_info=True)
            error_content = error.content.decode() if isinstance(error.content, bytes) else str(error.content)
            log_event("CALENDAR_CREATE_API_ERROR", f"API Error: {error.resp.status} - {error._get_reason()}", error_content)
            # TODO: If error is 409 (conflict), trigger conflict notification (Step 12)
            # For now, just log. Need to parse error content to confirm it's a conflict.
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating Google Calendar event: {e}", exc_info=True)
            log_event("CALENDAR_CREATE_UNEXPECTED_ERROR", f"Unexpected error: {e}")
            return None

    # TODO: Implement conflict checking (check_conflict method) if required by plan.
    # This can be complex, involving querying events around the time or using free/busy API.

# Placeholder for a script to guide user through OAuth2 to get refresh_token
# This would typically be a separate utility script.
def get_refresh_token_instructions():
    """
    Provides instructions or runs a flow to get a refresh token.
    This is a manual one-time step for the user.
    """
    # 1. User creates OAuth 2.0 credentials (Desktop app type) in Google Cloud Console.
    #    Gets client_id, client_secret. Downloads `credentials.json`.
    # 2. Run a script like this (simplified example):
    #    flow = InstalledAppFlow.from_client_secrets_file('path/to/your/client_secret.json', SCOPES)
    #    flow.run_local_server(port=0) # or run_console()
    #    refresh_token = flow.credentials.refresh_token
    #    Store this refresh_token in .env.assistant
    pass

if __name__ == '__main__':
    # Basic test (requires GOOGLE_* env vars to be set in .env.assistant or environment)
    # And a valid refresh token previously obtained.
    async def test_calendar_handler():
        logging.basicConfig(level=logging.INFO)
        from dotenv import load_dotenv
        from pathlib import Path

        # Load .env for local testing
        env_path = Path(__file__).parent.parent / '.env.assistant'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            global settings # Re-initialize settings if .env was just loaded
            settings = settings.__class__()
            if not all([settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET, settings.GOOGLE_REFRESH_TOKEN]):
                print("Google credentials not fully set in .env.assistant. Test may fail or be skipped.")
                print("Please run the OAuth flow to get a refresh token and set GOOGLE_REFRESH_TOKEN.")
                print("Client ID and Secret should also be set from your Google Cloud project.")
                # return
        else:
            print(f"{env_path} not found. Ensure env vars are set for testing.")
            # return

        handler = GoogleCalendarHandler()

        # Ensure creds can be obtained
        if not handler._get_credentials():
            print("Failed to get Google credentials. Exiting test.")
            return

        # Example data for creating an event
        # Make sure service_datetime_obj_cst is in the future for event creation
        now_cst_test = datetime.datetime.now(pytz.timezone('America/Chicago'))
        future_service_time = now_cst_test + datetime.timedelta(days=1, hours=2)

        sample_data_for_event = {
            "authorization_id": "CALTEST001",
            "client_name": "Calendar Test Client",
            "client_email": "caltest@example.com",
            "service_datetime_obj_cst": future_service_time,
            "patient_name": "Test Patient X",
            "service_location_address": "100 Google Way, Mountain View, CA",
            "original_email_subject": "Calendar Test Event Subject"
        }

        print(f"Attempting to create event for {sample_data_for_event['authorization_id']} at {future_service_time.isoformat()}")
        event_id = await handler.create_event(sample_data_for_event)
        if event_id:
            print(f"Test event created successfully! Event ID: {event_id}")
        else:
            print("Failed to create test event.")

    # asyncio.run(test_calendar_handler())
    print("GoogleCalendarHandler created. Run test_calendar_handler() manually if configured.")
    print("Remember to get a refresh token via OAuth2 flow and set appropriate GOOGLE_* env vars.")
