import requests
import logging
from typing import Dict, Any, Optional
from .config import settings

logger = logging.getLogger(__name__)

class InvoiceGenerator:
    def __init__(self):
        self.base_url = settings.INVOICE_NINJA_URL.rstrip('/')
        self.headers = {
            'X-Ninja-Token': settings.INVOICE_NINJA_TOKEN,
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    
    def create_client(self, client_data: Dict[str, Any]) -> Optional[str]:
        """Create a new client in InvoiceNinja"""
        try:
            url = f"{self.base_url}/api/v1/clients"
            response = requests.post(url, json=client_data, headers=self.headers)
            response.raise_for_status()
            return response.json().get('data', {}).get('id')
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating client: {str(e)}")
            return None
    
    def find_client_by_email(self, email: str) -> Optional[str]:
        """Find a client by email in InvoiceNinja"""
        try:
            url = f"{self.base_url}/api/v1/clients?email={email}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                return data['data'][0]['id']
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error finding client: {str(e)}")
            return None
    
    def create_invoice(self, invoice_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new invoice in InvoiceNinja"""
        try:
            # First, handle client
            client_email = invoice_data.get('client_email')
            if not client_email:
                logger.error("No client email provided in invoice data")
                return None
                
            # Check if client exists
            client_id = self.find_client_by_email(client_email)
            
            # If client doesn't exist, create them
            if not client_id:
                client_data = {
                    'name': invoice_data.get('client_name', 'New Client'),
                    'contacts': [
                        {
                            'first_name': invoice_data.get('client_name', '').split(' ')[0],
                            'last_name': ' '.join(invoice_data.get('client_name', '').split(' ')[1:]),
                            'email': client_email,
                            'send_email': True
                        }
                    ]
                }
                client_id = self.create_client(client_data)
                if not client_id:
                    logger.error("Failed to create client")
                    return None
            
            # Prepare invoice items
            line_items = []
            for item in invoice_data.get('items', []):
                line_items.append({
                    'product_key': item.get('description', 'Service'),
                    'notes': item.get('description', ''),
                    'cost': float(item.get('price', 0)),
                    'qty': int(item.get('quantity', 1))
                })
            
            # Create invoice payload
            payload = {
                'client_id': client_id,
                'line_items': line_items,
                'due_date': invoice_data.get('due_date'),
                'public_notes': invoice_data.get('notes', ''),
                'auto_bill_enabled': True
            }
            
            # Send request to create invoice
            url = f"{self.base_url}/api/v1/invoices"
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            
            # Return the created invoice data
            return response.json().get('data')
            
        except Exception as e:
            logger.error(f"Error creating invoice: {str(e)}")
            return None
    
    def send_invoice_email(self, invoice_id: str, email: str) -> bool:
        """Send the invoice via email to the client"""
        try:
            url = f"{self.base_url}/api/v1/emails"
            payload = {
                'entity': 'invoice',
                'entity_id': invoice_id,
                'template': 'invoice',
                'subject': 'Your Invoice',
                'body': 'Please find attached your invoice.',
                'to': email
            }
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error sending invoice email: {str(e)}")
            return False
