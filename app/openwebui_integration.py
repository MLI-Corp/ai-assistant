import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel

from .email_processor import EmailProcessor
from .invoice_ninja import InvoiceNinjaClient, get_invoice_ninja_client
from .config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/openwebui", tags=["openwebui"])

class EmailQuery(BaseModel):
    query: str
    limit: int = 10

class InvoiceQuery(BaseModel):
    query: str
    status: Optional[str] = None
    limit: int = 10

@router.post("/email/search")
async def search_emails(query: EmailQuery):
    """
    Search emails based on the provided query
    """
    try:
        processor = EmailProcessor()
        # This is a placeholder - you'll need to implement the search_emails method
        # in your EmailProcessor class
        results = await processor.search_emails(query.query, limit=query.limit)
        return {"results": results}
    except Exception as e:
        logger.error(f"Error searching emails: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search emails"
        )

@router.get("/emails/{email_id}")
async def get_email(email_id: str):
    """
    Get details of a specific email by ID
    """
    try:
        processor = EmailProcessor()
        # This is a placeholder - you'll need to implement the get_email method
        # in your EmailProcessor class
        email = await processor.get_email(email_id)
        if not email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email not found"
            )
        return email
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch email"
        )

@router.get("/invoices")
async def get_invoices(
    status: Optional[str] = None,
    limit: int = 10,
    ninja_client: InvoiceNinjaClient = Depends(get_invoice_ninja_client)
):
    """
    Get a list of invoices from InvoiceNinja
    """
    try:
        invoices = await ninja_client.get_invoices(status=status, limit=limit)
        return {"invoices": invoices}
    except Exception as e:
        logger.error(f"Error fetching invoices: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch invoices"
        )

@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    ninja_client: InvoiceNinjaClient = Depends(get_invoice_ninja_client)
):
    """
    Get details of a specific invoice by ID
    """
    try:
        invoice = await ninja_client.get_invoice(invoice_id)
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found"
            )
        return invoice
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching invoice: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch invoice"
        )

# Function to get OpenAPI schema for the LLM
def get_openai_functions():
    """
    Return the function definitions for the LLM to use
    """
    return [
        {
            "name": "search_emails",
            "description": "Search for emails based on a query",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for emails"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "get_email",
            "description": "Get details of a specific email by ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "ID of the email to retrieve"
                    }
                },
                "required": ["email_id"]
            }
        },
        {
            "name": "get_invoices",
            "description": "Get a list of invoices from InvoiceNinja",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter invoices by status (e.g., 'draft', 'sent', 'paid')",
                        "enum": ["draft", "sent", "paid", "partial", "overdue", "unpaid"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of invoices to return",
                        "default": 10
                    }
                }
            }
        },
        {
            "name": "get_invoice",
            "description": "Get details of a specific invoice by ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_id": {
                        "type": "string",
                        "description": "ID of the invoice to retrieve"
                    }
                },
                "required": ["invoice_id"]
            }
        }
    ]
