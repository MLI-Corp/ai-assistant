import httpx
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, HttpUrl
from datetime import datetime
from .config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InvoiceNinjaClient:
    """Client for interacting with the InvoiceNinja API."""
    
    def __init__(self, base_url: str = None, api_token: str = None):
        """Initialize the InvoiceNinja client.
        
        Args:
            base_url: Base URL of the InvoiceNinja instance
            api_token: API token for authentication
        """
        self.base_url = base_url or settings.INVOICE_NINJA_URL.rstrip('/')
        self.api_token = api_token or settings.INVOICE_NINJA_TOKEN
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                'X-API-TOKEN': self.api_token,
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            timeout=30.0
        )
        logger.info(f"Initialized InvoiceNinja client for {self.base_url}")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an authenticated request to the InvoiceNinja API."""
        url = f"/api/v1/{endpoint.lstrip('/')}"
        logger.debug(f"Making {method} request to {url}")
        
        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"API request failed with status {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            raise
    
    # Client Operations
    async def get_clients(self, query: str = None) -> List[Dict[str, Any]]:
        """Get a list of clients."""
        params = {}
        if query:
            params['filter'] = query
        response = await self._request('GET', 'clients', params=params)
        return response.get('data', [])
    
    async def create_client(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new client."""
        return await self._request('POST', 'clients', json=client_data)
    
    # Task Operations
    async def create_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task."""
        return await self._request('POST', 'tasks', json=task_data)
    
    async def get_tasks(self, status: str = None) -> List[Dict[str, Any]]:
        """Get a list of tasks."""
        params = {}
        if status:
            params['status'] = status
        response = await self._request('GET', 'tasks', params=params)
        return response.get('data', [])
    
    # Invoice Operations
    async def create_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new invoice."""
        return await self._request('POST', 'invoices', json=invoice_data)
    
    async def get_invoices(self, status: str = None) -> List[Dict[str, Any]]:
        """Get a list of invoices."""
        params = {}
        if status:
            params['status'] = status
        response = await self._request('GET', 'invoices', params=params)
        return response.get('data', [])
    
    # Email Operations
    async def send_email(self, entity_type: str, entity_id: str, template: str = 'invoice') -> Dict[str, Any]:
        """Send an email for an entity (invoice, quote, etc.)."""
        return await self._request('POST', f'emails?entity={entity_type}&entity_id={entity_id}&template={template}')

# Helper function to get a client instance
async def get_invoice_ninja_client() -> InvoiceNinjaClient:
    """Get an InvoiceNinja client instance for dependency injection."""
    client = InvoiceNinjaClient()
    try:
        yield client
    finally:
        await client.close()
