import sqlite3
import logging
from pathlib import Path
from .config import settings

logger = logging.getLogger(__name__)

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    db_path = Path(settings.SQLITE_DB_PATH)
    # Ensure the directory for the database file exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, check_same_thread=False) # check_same_thread=False for FastAPI background tasks
    conn.row_factory = sqlite3.Row # Access columns by name
    return conn

def initialize_db():
    """Initializes the database and creates tables if they don't exist."""
    logger.info(f"Initializing database at {settings.SQLITE_DB_PATH}...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create event_logs table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT NOT NULL, -- e.g., 'EMAIL_PROCESSED', 'INVOICE_CREATED', 'ERROR', 'GEOCODE_CACHE_HIT'
            message TEXT NOT NULL,
            details TEXT -- Optional JSON blob for more details
        )
        """)
        logger.info("Table 'event_logs' checked/created.")

        # Create geocoding_cache table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS geocoding_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_address TEXT UNIQUE NOT NULL, -- The address string queried
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            full_response TEXT, -- Store the full JSON response from Nominatim if needed
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        logger.info("Table 'geocoding_cache' checked/created.")

        # Create client_billing_rates table (optional, can also use JSON config)
        # For now, this is just a placeholder schema if you want to use DB for rates
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS client_billing_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_identifier TEXT UNIQUE NOT NULL, -- e.g., email, name, or specific ID
            rate_type TEXT NOT NULL, -- e.g., 'hourly', 'mileage'
            rate_value REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        logger.info("Table 'client_billing_rates' checked/created.")


        conn.commit()
        logger.info("Database initialization complete.")
    except sqlite3.Error as e:
        logger.error(f"SQLite error during initialization: {e}")
        raise
    finally:
        if conn:
            conn.close()

# --- Helper functions for logging ---
def log_event(event_type: str, message: str, details: Optional[str] = None):
    """Logs an event to the event_logs table."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO event_logs (event_type, message, details) VALUES (?, ?, ?)",
            (event_type, message, details)
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Failed to log event '{event_type}': {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # For manual initialization or testing
    print(f"Attempting to initialize database: {settings.SQLITE_DB_PATH}")
    initialize_db()
    print("Manual initialization script finished.")
    # Example log
    log_event("MANUAL_INIT", "Database manually initialized via script.")
    conn = get_db_connection()
    for row in conn.execute("SELECT * FROM event_logs"):
        print(dict(row))
    conn.close()
