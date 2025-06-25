from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "Backend Assistant"
    DEBUG: bool = False
    BASE_URL: str = "http://localhost:8001" # Assistant's own URL

    # Logging
    LOG_LEVEL: str = "INFO"

    # IMAP Settings (for Zoho or other email provider)
    IMAP_HOST: str
    IMAP_PORT: int = 993
    IMAP_USER: str
    IMAP_PASSWORD: str # Use App Specific Password if 2FA is enabled
    EMAIL_POLL_INTERVAL: int = 30 # Seconds, fallback if IDLE not effective

    # InvoiceNinja Settings (for local instance)
    INVOICENINJA_URL: str # e.g., http://invoiceninja:9000 or http://localhost:9000 if mapped
    INVOICENINJA_API_TOKEN: str
    # Path to client billing rates JSON file (mounted into Docker)
    CLIENT_BILLING_RATES_PATH: str = "/app/config/client_billing_rates.json"


    # Google Calendar API Settings (OAuth 2.0 for user accounts)
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REFRESH_TOKEN: Optional[str] = None # Store user's refresh token here
    GOOGLE_CALENDAR_ID: str = "primary" # Calendar ID to use, e.g., 'primary' or specific calendar_id@group.calendar.google.com
    # The following is for service accounts, which is an alternative but harder for personal Gmail.
    # GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None # Path to service account key file for domain-wide delegation

    # Notification Webhook
    NOTIFICATION_WEBHOOK_URL: Optional[str] = None # URL to send POST notifications

    # Geocoding API (Nominatim - public instance, use with caution for rate limits)
    GEOCODING_API_URL: str = "https://nominatim.openstreetmap.org/search"
    GEOCODING_USER_AGENT: str = "BackendAssistant/0.1 (ai@assistant.dev; for address geocoding)"


    # SQLite Database
    SQLITE_DB_PATH: str = "/app/data/assistant.db" # Path inside the container

    # Model configuration for Pydantic
    model_config = SettingsConfigDict(env_file=".env.assistant", extra="ignore")

settings = Settings()
