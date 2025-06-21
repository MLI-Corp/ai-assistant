import logging
import asyncio
from typing import Dict, Any, List, Optional
from .invoice_ninja import InvoiceNinjaClient, get_invoice_ninja_client
from .config import settings

logger = logging.getLogger(__name__)

class InvoiceLLMProcessor:
    """Processor for handling LLM-driven invoice operations."""
    
    def __init__(self):
        self.ninja_client = None
    
    async def get_ninja_client(self) -> InvoiceNinjaClient:
        """Get or create InvoiceNinja client."""
        if not self.ninja_client:
            self.ninja_client = InvoiceNinjaClient()
        return self.ninja_client
    
    async def close(self):
        """Close the InvoiceNinja client."""
        if self.ninja_client:
            await self.ninja_client.close()
    
    async def create_invoice(self, description: str, amount: float, client_name: str = None, 
                           client_email: str = None, due_date: str = None) -> Dict[str, Any]:
        """Create an invoice from LLM request."""
        try:
            client = await self.get_ninja_client()
            result = await client.create_invoice_from_text(
                description=description,
                amount=amount,
                client_name=client_name,
                client_email=client_email,
                due_date=due_date
            )
            return {
                "success": True,
                "message": f"Invoice created successfully for ${amount}",
                "invoice_id": result.get('data', {}).get('id'),
                "invoice": result
            }
        except Exception as e:
            logger.error(f"Error creating invoice: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to create invoice: {str(e)}"
            }
    
    async def get_invoices(self, status: str = None, limit: int = 10) -> Dict[str, Any]:
        """Get invoices from LLM request."""
        try:
            client = await self.get_ninja_client()
            invoices = await client.get_invoices(status=status, limit=limit)
            return {
                "success": True,
                "invoices": invoices,
                "count": len(invoices)
            }
        except Exception as e:
            logger.error(f"Error fetching invoices: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to fetch invoices: {str(e)}"
            }
    
    async def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Get specific invoice from LLM request."""
        try:
            client = await self.get_ninja_client()
            invoice = await client.get_invoice(invoice_id)
            if not invoice:
                return {
                    "success": False,
                    "message": f"Invoice {invoice_id} not found"
                }
            return {
                "success": True,
                "invoice": invoice
            }
        except Exception as e:
            logger.error(f"Error fetching invoice: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to fetch invoice: {str(e)}"
            }
    
    async def mark_invoice_sent(self, invoice_id: str) -> Dict[str, Any]:
        """Mark invoice as sent from LLM request."""
        try:
            client = await self.get_ninja_client()
            result = await client.mark_invoice_as_sent(invoice_id)
            return {
                "success": True,
                "message": f"Invoice {invoice_id} marked as sent",
                "result": result
            }
        except Exception as e:
            logger.error(f"Error marking invoice as sent: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to mark invoice as sent: {str(e)}"
            }
    
    async def mark_invoice_paid(self, invoice_id: str) -> Dict[str, Any]:
        """Mark invoice as paid from LLM request."""
        try:
            client = await self.get_ninja_client()
            result = await client.mark_invoice_as_paid(invoice_id)
            return {
                "success": True,
                "message": f"Invoice {invoice_id} marked as paid",
                "result": result
            }
        except Exception as e:
            logger.error(f"Error marking invoice as paid: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to mark invoice as paid: {str(e)}"
            }
    
    async def get_clients(self, query: str = None) -> Dict[str, Any]:
        """Get clients from LLM request."""
        try:
            client = await self.get_ninja_client()
            clients = await client.get_clients(query=query)
            return {
                "success": True,
                "clients": clients,
                "count": len(clients)
            }
        except Exception as e:
            logger.error(f"Error fetching clients: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to fetch clients: {str(e)}"
            }
    
    async def process_llm_function_call(self, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Process LLM function calls for invoice operations."""
        try:
            if function_name == "create_invoice":
                return await self.create_invoice(
                    description=arguments.get("description"),
                    amount=arguments.get("amount"),
                    client_name=arguments.get("client_name"),
                    client_email=arguments.get("client_email"),
                    due_date=arguments.get("due_date")
                )
            elif function_name == "get_invoices":
                return await self.get_invoices(
                    status=arguments.get("status"),
                    limit=arguments.get("limit", 10)
                )
            elif function_name == "get_invoice":
                return await self.get_invoice(arguments.get("invoice_id"))
            elif function_name == "mark_invoice_sent":
                return await self.mark_invoice_sent(arguments.get("invoice_id"))
            elif function_name == "mark_invoice_paid":
                return await self.mark_invoice_paid(arguments.get("invoice_id"))
            elif function_name == "get_clients":
                return await self.get_clients(arguments.get("query"))
            else:
                return {
                    "success": False,
                    "message": f"Unknown function: {function_name}"
                }
        except Exception as e:
            logger.error(f"Error processing LLM function call {function_name}: {str(e)}")
            return {
                "success": False,
                "message": f"Error processing {function_name}: {str(e)}"
            }

# Global instance for easy access
_invoice_llm_processor = None

async def get_invoice_llm_processor() -> InvoiceLLMProcessor:
    """Get the global InvoiceLLMProcessor instance."""
    global _invoice_llm_processor
    if _invoice_llm_processor is None:
        _invoice_llm_processor = InvoiceLLMProcessor()
    return _invoice_llm_processor 