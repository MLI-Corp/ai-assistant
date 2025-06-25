import logging
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect # Added WebSocket
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
import datetime # For LogEntry model

from pydantic import BaseModel # For LogEntry model

from .config import settings
from . import database # Import the module itself for get_db_connection and sqlite3
from .database import initialize_db, log_event # Specific imports for these functions
from .email_handler import EmailHandler


# Configure logging
logger = logging.getLogger(__name__)

# Global instance for the email handler, managed by lifespan
email_handler_instance: Optional[EmailHandler] = None
# connection_manager is already global

@asynccontextmanager
async def lifespan(app: FastAPI): # app: FastAPI is conventional, not strictly needed if not used
    global email_handler_instance, connection_manager
    # Startup
    logger.info(f"Starting {settings.APP_NAME}...")
    await connection_manager.broadcast(f"INFO: {settings.APP_NAME} is starting up...")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Log level: {settings.LOG_LEVEL}")

    # Initialize database
    try:
        initialize_db()
        logger.info("Database initialized successfully.")
        log_event("STARTUP", f"{settings.APP_NAME} database initialized.")
        await connection_manager.broadcast("INFO: Database initialized.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        await connection_manager.broadcast(f"ERROR: Database initialization failed: {e}")


    # Initialize and start email handler if IMAP host is configured
    if settings.IMAP_HOST:
        # Pass the connection_manager to EmailHandler
        email_handler_instance = EmailHandler(websocket_manager=connection_manager)
        await email_handler_instance.start_monitoring()
        log_event("EMAIL_MONITOR_STARTED", "Email monitoring service started.")
        # This message is now sent from EmailHandler.start_monitoring potentially
    else:
        logger.warning("IMAP_HOST not configured. Email monitoring will not start.")
        log_event("EMAIL_MONITOR_SKIPPED", "IMAP_HOST not configured, email monitoring skipped.")
        await connection_manager.broadcast(f"WARNING: {settings.APP_NAME} email monitoring NOT started (IMAP_HOST not configured).")

    yield
    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}...")
    await connection_manager.broadcast(f"INFO: {settings.APP_NAME} is shutting down...")
    if email_handler_instance:
        logger.info("Stopping email monitor...")
        await email_handler_instance.stop_monitoring()
        log_event("EMAIL_MONITOR_STOPPED", "Email monitoring service stopped.")
        # Message broadcast from EmailHandler.stop_monitoring potentially

    log_event("SHUTDOWN", f"{settings.APP_NAME} shut down successfully.")

    # Close all active WebSocket connections on shutdown
    active_conns_at_shutdown = list(connection_manager.active_connections) # Iterate over a copy
    for ws in active_conns_at_shutdown:
        try:
            logger.info(f"Closing WebSocket connection during shutdown: {ws.client}")
            await ws.close(code=1001, reason="Server shutting down") # Going away
        except Exception as e:
            logger.warning(f"Error closing WebSocket {ws.client} during shutdown: {e}")
    if active_conns_at_shutdown:
        logger.info(f"{len(active_conns_at_shutdown)} active WebSocket connection(s) closed during shutdown.")

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    debug=settings.DEBUG,
    lifespan=lifespan
)

@app.get("/health", summary="Health Check", tags=["General"])
async def health_check():
    """Health check endpoint to confirm the API is running."""
    return {"status": "ok", "app_name": settings.APP_NAME, "version": "0.1.0"}

# --- Control Endpoints for OpenWebUI ---
@app.post("/control/start_monitoring", summary="Start Email Monitoring", tags=["Control"])
async def start_email_monitoring_endpoint():
    global email_handler_instance
    if not settings.IMAP_HOST:
        raise HTTPException(status_code=400, detail="IMAP_HOST not configured. Cannot start monitoring.")

    if email_handler_instance and not email_handler_instance._stop_event.is_set():
        return {"status": "already_running", "message": "Email monitoring is already active."}

    logger.info("Received request to START email monitoring.")
    if not email_handler_instance:
        email_handler_instance = EmailHandler()

    await email_handler_instance.start_monitoring()
    log_event("CONTROL_ACTION", "Email monitoring started via API.")
    return {"status": "starting", "message": "Email monitoring initiated."}

@app.post("/control/stop_monitoring", summary="Stop Email Monitoring", tags=["Control"])
async def stop_email_monitoring_endpoint():
    global email_handler_instance
    if not email_handler_instance or email_handler_instance._stop_event.is_set():
        return {"status": "already_stopped", "message": "Email monitoring is not active or already stopping."}

    logger.info("Received request to STOP email monitoring.")
    await email_handler_instance.stop_monitoring()
    log_event("CONTROL_ACTION", "Email monitoring stopped via API.")
    return {"status": "stopping", "message": "Email monitoring stopping."}

@app.get("/control/status", summary="Get Assistant Status", tags=["Control"])
async def get_assistant_status():
    global email_handler_instance
    monitoring_active = False
    status_message = "Email monitoring is disabled (IMAP_HOST not configured)."

    if settings.IMAP_HOST:
        if email_handler_instance and not email_handler_instance._stop_event.is_set():
            monitoring_active = True
            status_message = "Email monitoring is active."
        else:
            monitoring_active = False
            status_message = "Email monitoring is stopped or initializing."
            if not email_handler_instance:
                 status_message = "Email monitoring is initializing."

    return {
        "monitoring_active": monitoring_active,
        "status_message": status_message,
        "imap_configured": bool(settings.IMAP_HOST)
    }

# --- Log/Summary Endpoint ---
class LogEntry(BaseModel):
    id: int
    timestamp: datetime.datetime
    event_type: str
    message: str
    details: Optional[str] = None

@app.get("/logs", summary="Get Event Logs", response_model=List[LogEntry], tags=["Logs"])
async def get_event_logs(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    """Retrieve event logs from the assistant's database."""
    conn = None
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, timestamp, event_type, message, details FROM event_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        logs_raw = cursor.fetchall()
        logs = [LogEntry(**dict(row)) for row in logs_raw]
        return logs
    except database.sqlite3.Error as e:
        logger.error(f"SQLite error fetching logs: {e}")
        raise HTTPException(status_code=500, detail="Error fetching logs from database.")
    except Exception as e:
        logger.error(f"Unexpected error fetching logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unexpected error fetching logs.")
    finally:
        if conn:
            conn.close()

# --- WebSocket Connection Manager and Endpoint ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected: {websocket.client}")
        await websocket.send_text("INFO: Connection established. Waiting for status updates...")


    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected: {websocket.client}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.warning(f"Failed to send personal message to {websocket.client}: {e}")


    async def broadcast(self, message: str):
        logger.debug(f"Broadcasting WebSocket message: '{message}' to {len(self.active_connections)} connection(s)")
        # Create a list of tasks for sending messages
        tasks = []
        # Iterate over a copy of the list if connections might be removed during iteration
        for connection in list(self.active_connections):
            tasks.append(connection.send_text(message))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Handle broken connections
                closed_connection = list(self.active_connections)[i] # Assuming order is maintained
                logger.warning(f"Error sending WebSocket message to {closed_connection.client}: {result}. Removing connection.")
                if closed_connection in self.active_connections:
                     self.active_connections.remove(closed_connection)


connection_manager = ConnectionManager()

@app.websocket("/ws/status")
async def websocket_status_endpoint(websocket: WebSocket):
    await connection_manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive, server sends updates, client mostly listens
            # Optionally, client can send pings or specific requests here
            data = await websocket.receive_text()
            logger.debug(f"Received from WebSocket {websocket.client}: {data}")
            if data == "ping": # Simple keep-alive
                await websocket.send_text("pong")
            # Add more sophisticated client-server interaction if needed
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket handler for {websocket.client}: {e}", exc_info=True)
        connection_manager.disconnect(websocket) # Ensure cleanup


if __name__ == "__main__":
    import uvicorn
    # Need to import asyncio for gather if not already at top
    import asyncio
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level=settings.LOG_LEVEL.lower())
