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
    
    async def get_countries(self) -> List[Dict[str, Any]]:
        """Get a list of countries."""
        try:
            response = await self._request('GET', 'countries')
            return response.get('data', [])
        except Exception as e:
            logger.warning(f"Could not fetch countries: {str(e)}. Using default country.")
            # Return a default country structure if the endpoint doesn't exist
            return [{'id': 1, 'name': 'United States'}]
    
    async def create_client(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new client."""
        return await self._request('POST', 'clients', json=client_data)
    
    async def create_client_with_valid_country(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new client without country_id to avoid validation errors."""
        # Remove country_id to avoid validation issues
        client_data.pop('country_id', None)
        return await self.create_client(client_data)
    
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
    
    async def create_invoice_from_text(self, description: str, amount: float, client_name: str = None, 
                                     client_email: str = None, due_date: str = None) -> Dict[str, Any]:
        """Create an invoice from natural language description."""
        # First, ensure we have a client
        client_id = None
        if client_name or client_email:
            # Try to find existing client
            clients = await self.get_clients()
            for client in clients:
                if (client_name and client.get('name', '').lower() == client_name.lower()) or \
                   (client_email and client.get('email', '').lower() == client_email.lower()):
                    client_id = client['id']
                    break
            
            # Create client if not found
            if not client_id:
                client_data = {
                    'name': client_name or 'Unknown Client',
                    'email': client_email or '',
                    'phone': '',
                    'address1': '',
                    'address2': '',
                    'city': '',
                    'state': '',
                    'postal_code': ''
                }
                client_response = await self.create_client_with_valid_country(client_data)
                client_id = client_response['data']['id']
        
        # Create invoice data
        invoice_data = {
            'client_id': client_id,
            'line_items': [
                {
                    'product_key': 'Service',
                    'notes': description,
                    'cost': amount,
                    'qty': 1,
                    'tax_name1': '',
                    'tax_rate1': 0
                }
            ],
            'status_id': 1,  # Draft status
            'due_date': due_date or None
        }
        
        return await self.create_invoice(invoice_data)
    
    async def get_invoices(self, status: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get a list of invoices."""
        params = {'per_page': limit}
        if status:
            params['status'] = status
        response = await self._request('GET', 'invoices', params=params)
        return response.get('data', [])
    
    async def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific invoice by ID."""
        try:
            response = await self._request('GET', f'invoices/{invoice_id}')
            return response.get('data')
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    async def update_invoice(self, invoice_id: str, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing invoice."""
        return await self._request('PUT', f'invoices/{invoice_id}', json=invoice_data)
    
    async def delete_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Delete an invoice."""
        return await self._request('DELETE', f'invoices/{invoice_id}')
    
    async def mark_invoice_as_sent(self, invoice_id: str) -> Dict[str, Any]:
        """Mark an invoice as sent."""
        return await self._request('POST', f'invoices/{invoice_id}/mark_sent')
    
    async def mark_invoice_as_paid(self, invoice_id: str) -> Dict[str, Any]:
        """Mark an invoice as paid."""
        return await self._request('POST', f'invoices/{invoice_id}/mark_paid')
    
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
