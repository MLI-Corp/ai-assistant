import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

# Local imports
from .config import Settings, settings
from .invoice_ninja import InvoiceNinjaClient, get_invoice_ninja_client
from .background import start_background_tasks, stop_background_tasks
from .openwebui_integration import router as openwebui_router

# Constants
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Create necessary directories
STATIC_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

# Initialize settings (already imported from .config)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Models
class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: str = settings.LLM_MODEL_NAME
    temperature: float = 0.7
    max_tokens: int = 1024
    stream: bool = False

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]

# Initialize FastAPI app
app = FastAPI(
    title="InvoiceNinja AI Assistant",
    description="AI Assistant for Invoice Ninja with LLM integration",
    on_startup=[start_background_tasks],
    on_shutdown=[stop_background_tasks],
    version="1.0.0",
    debug=settings.DEBUG
)

# Create API router
api_router = APIRouter(prefix="/api", tags=["api"])

# Include API routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(openwebui_router)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "your-secret-key-here"),
    session_cookie="invoiceninja_ai_session",
)

# Initialize templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Initialize HTTP client
http_client = httpx.AsyncClient()

# Event handlers
@app.on_event("startup")
async def startup_event():
    """Initialize services when the application starts."""
    logger.info("Starting up Invoice Ninja AI Assistant...")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources when the application shuts down."""
    logger.info("Shutting down Invoice Ninja AI Assistant...")
    await http_client.aclose()

# API Routes
@api_router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "version": "1.0.0",
        "llm_connected": bool(settings.LLM_API_BASE_URL),
        "invoiceninja_connected": bool(settings.INVOICE_NINJA_TOKEN)
    }

# InvoiceNinja API Routes
@api_router.get("/clients", response_model=List[Dict[str, Any]])
async def get_clients(
    ninja_client: InvoiceNinjaClient = Depends(get_invoice_ninja_client),
    search: Optional[str] = Query(None, description="Search term for clients")
):
    """Get a list of clients from InvoiceNinja"""
    try:
        clients = await ninja_client.get_clients(query=search)
        return clients
    except Exception as e:
        logger.error(f"Error fetching clients: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch clients")

@api_router.post("/clients", status_code=status.HTTP_201_CREATED)
async def create_client(
    client_data: Dict[str, Any],
    ninja_client: InvoiceNinjaClient = Depends(get_invoice_ninja_client)
):
    """Create a new client in InvoiceNinja"""
    try:
        result = await ninja_client.create_client(client_data)
        return result
    except Exception as e:
        logger.error(f"Error creating client: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create client")

@api_router.get("/tasks", response_model=List[Dict[str, Any]])
async def get_tasks(
    status: Optional[str] = Query(None, description="Filter tasks by status"),
    ninja_client: InvoiceNinjaClient = Depends(get_invoice_ninja_client)
):
    """Get a list of tasks from InvoiceNinja"""
    try:
        tasks = await ninja_client.get_tasks(status=status)
        return tasks
    except Exception as e:
        logger.error(f"Error fetching tasks: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch tasks")

@api_router.post("/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: Dict[str, Any],
    ninja_client: InvoiceNinjaClient = Depends(get_invoice_ninja_client)
):
    """Create a new task in InvoiceNinja"""
    try:
        result = await ninja_client.create_task(task_data)
        return result
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create task")

@api_router.get("/invoices", response_model=List[Dict[str, Any]])
async def get_invoices(
    status: Optional[str] = Query(None, description="Filter invoices by status"),
    ninja_client: InvoiceNinjaClient = Depends(get_invoice_ninja_client)
):
    """Get a list of invoices from InvoiceNinja"""
    try:
        invoices = await ninja_client.get_invoices(status=status)
        return invoices
    except Exception as e:
        logger.error(f"Error fetching invoices: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch invoices")

@api_router.post("/invoices", status_code=status.HTTP_201_CREATED)
async def create_invoice(
    invoice_data: Dict[str, Any],
    ninja_client: InvoiceNinjaClient = Depends(get_invoice_ninja_client)
):
    """Create a new invoice in InvoiceNinja"""
    try:
        result = await ninja_client.create_invoice(invoice_data)
        return result
    except Exception as e:
        logger.error(f"Error creating invoice: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create invoice")

# UI Routes
@app.get("/", response_class=HTMLResponse)
async def chat_ui(request: Request):
    """Serve the chat interface"""
    return templates.TemplateResponse("index.html", {"request": request, "title": "Invoice Ninja AI"})

# Signal handlers
def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("Shutting down...")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info" if settings.DEBUG else "warning"
    )
