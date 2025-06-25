# Backend Email Processing Assistant

This backend assistant is designed to monitor an email inbox for work authorization messages, extract relevant data, and integrate with other services like InvoiceNinja (for invoicing) and Google Calendar (for scheduling). It also provides notifications via a configurable webhook.

## Features

- **Email Monitoring**: Connects to an IMAP inbox (e.g., Zoho) to fetch and process new emails.
- **Data Extraction**: Identifies authorization emails and extracts details like Authorization ID, client information, service date/time, and mileage.
- **InvoiceNinja Integration**: Creates clients and invoices in a local InvoiceNinja v5 instance (configured with SQLite).
- **Google Calendar Integration**: Creates calendar events for future services on a specified Google Calendar.
- **Webhook Notifications**: Sends summaries of processing actions (successes, failures) to a configured webhook URL.
- **SQLite Database**: Uses a local SQLite database for operational logs, geocoding cache, and potentially client billing rates.
- **API & WebSockets**: Exposes FastAPI endpoints for status, control, and logs, plus a WebSocket for real-time status updates (intended for OpenWebUI integration).

## Configuration

The assistant is configured primarily through environment variables, typically loaded from a `.env.assistant` file placed in the `backend_assistant/` directory. A template is provided as `.env.assistant.template`.

**Key Configuration Variables:**

*   **IMAP Settings (`IMAP_HOST`, `IMAP_PORT`, `IMAP_USER`, `IMAP_PASSWORD`):** Credentials for the email account to monitor. For services like Zoho or Gmail with 2FA, an "App Specific Password" is usually required for `IMAP_PASSWORD`.
*   **InvoiceNinja Settings (`INVOICENINJA_URL`, `INVOICENINJA_API_TOKEN`):**
    *   `INVOICENINJA_URL`: The URL of your local InvoiceNinja v5 instance (e.g., `http://invoiceninja:9000` if running within the same Docker network).
    *   `INVOICENINJA_API_TOKEN`: An API token generated from your InvoiceNinja instance.
*   **Client Billing Rates (`CLIENT_BILLING_RATES_PATH`):**
    *   Path to a JSON file (mounted into the Docker container, default `/app/config/client_billing_rates.json`) that defines client-specific billing rates.
    *   **Format Example (`client_billing_rates.json`):**
      ```json
      {
        "default": {
          "hourly_rate": 75.00,
          "mileage_rate": 0.65
        },
        "client_email@example.com": {
          "hourly_rate": 85.00,
          "mileage_rate": 0.70,
          "fixed_service_fee": 50.00
        },
        "another_client_id_or_name": {
          "mileage_rate": 0.60
        }
      }
      ```
      The `DataExtractor` will look for a key matching the client's email or name. If not found, it falls back to `"default"`.
*   **Google Calendar API Settings (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `GOOGLE_CALENDAR_ID`):**
    *   `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`: Obtained from Google Cloud Console when setting up OAuth 2.0 credentials.
    *   `GOOGLE_REFRESH_TOKEN`: A refresh token obtained via a one-time manual OAuth 2.0 flow (see instructions below).
    *   `GOOGLE_CALENDAR_ID`: The ID of the Google Calendar to use (e.g., `primary` or a specific calendar email).
*   **Notification Webhook (`NOTIFICATION_WEBHOOK_URL`):** The URL to which JSON POST notifications will be sent.
*   **Database (`SQLITE_DB_PATH`):** Path within the container for the SQLite database file (default `/app/data/assistant.db`).
*   **Logging (`LOG_LEVEL`):** Set to `DEBUG`, `INFO`, `WARNING`, `ERROR`.

### Obtaining Google OAuth Refresh Token (One-Time Setup)

To allow the assistant to create Google Calendar events on your behalf without interactive logins, you need to obtain a refresh token once:

1.  **Google Cloud Console:**
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project or select an existing one.
    *   Enable the **Google Calendar API** for your project (APIs & Services > Library).
    *   Go to APIs & Services > Credentials.
    *   Click "+ CREATE CREDENTIALS" > "OAuth client ID".
    *   Choose "Desktop app" as the Application type. Give it a name (e.g., "BackendAssistantCalendar").
    *   Click "Create". You will get a **Client ID** and **Client Secret**. Copy these into your `.env.assistant` file.
    *   Download the JSON credentials file (often named `client_secret_....json`). This file contains your client ID and secret.

2.  **Generate Refresh Token (using a helper script):**
    *   You'll need a small Python script using the `google-auth-oauthlib` library. Create a temporary Python script (e.g., `get_google_refresh_token.py`) in a local environment where you have Python and the Google client libraries installed (`pip install google-api-python-client google-auth-oauthlib google-auth-httplib2`).
    *   **`get_google_refresh_token.py` example:**
      ```python
      from google_auth_oauthlib.flow import InstalledAppFlow

      # Scopes required by the application
      SCOPES = ['https://www.googleapis.com/auth/calendar.events']
      # Path to your downloaded client_secret JSON file
      CLIENT_SECRETS_FILE = "path/to/your/client_secret_....json"

      flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
      # This will open a browser window for you to authorize the application.
      # After authorization, it will print credentials including the refresh_token.
      creds = flow.run_local_server(port=0)

      print("\n--- Credentials ---")
      print(f"Access Token: {creds.token}")
      print(f"Refresh Token: {creds.refresh_token}") # <--- COPY THIS VALUE
      print(f"Token URI: {creds.token_uri}")
      print(f"Client ID: {creds.client_id}")
      print(f"Client Secret: {creds.client_secret}")
      print("\nCopy the Refresh Token and add it to your .env.assistant file as GOOGLE_REFRESH_TOKEN.")
      ```
    *   Replace `"path/to/your/client_secret_....json"` with the actual path to your downloaded JSON file.
    *   Run this script (`python get_google_refresh_token.py`). It will open a browser window. Log in with the Google account whose calendar you want the assistant to manage. Grant the requested permissions.
    *   After successful authorization, the script will print credentials to your console, including the `Refresh Token`. Copy this `Refresh Token` value and paste it into your `.env.assistant` file for the `GOOGLE_REFRESH_TOKEN` variable.

    **Important Security Note:** Treat your `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and especially the `GOOGLE_REFRESH_TOKEN` as sensitive secrets.

## Running with Docker Compose

This assistant is designed to be run as part of the main `docker-compose.yml` setup for the project. Ensure its service definition is correctly configured there, pointing to this `backend_assistant` directory for the build context and using the `.env.assistant` file.

## Troubleshooting

*   **IMAP Connection Issues:**
    *   Verify `IMAP_HOST`, `IMAP_PORT`, `IMAP_USER`, and `IMAP_PASSWORD` are correct.
    *   Ensure your email provider allows IMAP access.
    *   If using 2FA, make sure `IMAP_PASSWORD` is an App Specific Password.
    *   Check Docker container logs for specific error messages from `imaplib`.
*   **InvoiceNinja API Issues:**
    *   Ensure `INVOICENINJA_URL` is correct and reachable from the assistant container (e.g., `http://invoiceninja:9000`).
    *   Verify `INVOICENINJA_API_TOKEN` is valid and has necessary permissions.
*   **Google Calendar Issues:**
    *   Confirm `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN` are correctly set.
    *   Ensure the Google Calendar API is enabled in your Google Cloud Project.
    *   Check that the `GOOGLE_CALENDAR_ID` is correct.
    *   The user who authorized the OAuth flow (whose refresh token is used) must have write access to the target calendar.
*   **Data Extraction Problems:**
    *   The current data extraction relies on specific keywords and regex patterns. If emails have different formats, these may need adjustment in `backend_assistant/app/data_extractor.py`.
    *   Check logs for messages about why an email might not be considered an authorization email or why specific fields couldn't be extracted.
*   **General:**
    *   Check the assistant's container logs: `docker-compose logs backend_assistant`.
    *   Check the SQLite database (`event_logs` table) via the `/logs` API endpoint or by accessing the database file directly from the Docker volume.
```
