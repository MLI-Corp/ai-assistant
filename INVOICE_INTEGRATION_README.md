# InvoiceNinja Integration for OpenWebUI

This integration allows your LLM models to create and manage invoices through InvoiceNinja programmatically.

## Features

- ✅ Create invoices from natural language descriptions
- ✅ Manage clients (create new ones automatically)
- ✅ List and retrieve invoices
- ✅ Mark invoices as sent or paid
- ✅ Full LLM function calling support
- ✅ REST API endpoints for direct access

## Configuration

The integration is configured with your InvoiceNinja instance:

- **URL**: `http://localhost:9000`
- **API Token**: `TtJU3xsyin9K4Ne1N8swAIqCZMHXjY32Ol9nrNL6NLbbr8EIPpv4fugZqHRjRrPb`

## API Endpoints

### Invoice Management

- `POST /api/v1/openwebui/invoices/create` - Create a new invoice
- `GET /api/v1/openwebui/invoices` - List invoices
- `GET /api/v1/openwebui/invoices/{invoice_id}` - Get specific invoice
- `POST /api/v1/openwebui/invoices/{invoice_id}/mark-sent` - Mark invoice as sent
- `POST /api/v1/openwebui/invoices/{invoice_id}/mark-paid` - Mark invoice as paid

### Client Management

- `GET /api/v1/openwebui/clients` - List clients

## LLM Function Calling

Your LLM can now use these functions:

### Create Invoice
```json
{
  "name": "create_invoice",
  "description": "Create a new invoice with description, amount, and optional client details",
  "parameters": {
    "type": "object",
    "properties": {
      "description": {
        "type": "string",
        "description": "Description of the service or product being invoiced"
      },
      "amount": {
        "type": "number",
        "description": "Amount to charge (in dollars)"
      },
      "client_name": {
        "type": "string",
        "description": "Name of the client (will create new client if doesn't exist)"
      },
      "client_email": {
        "type": "string",
        "description": "Email of the client"
      },
      "due_date": {
        "type": "string",
        "description": "Due date for the invoice (YYYY-MM-DD format)"
      }
    },
    "required": ["description", "amount"]
  }
}
```

### Get Invoices
```json
{
  "name": "get_invoices",
  "description": "Get a list of invoices from InvoiceNinja",
  "parameters": {
    "type": "object",
    "properties": {
      "status": {
        "type": "string",
        "description": "Filter invoices by status (e.g., 'draft', 'sent', 'paid')"
      },
      "limit": {
        "type": "integer",
        "description": "Maximum number of invoices to return",
        "default": 10
      }
    }
  }
}
```

### Mark Invoice as Sent/Paid
```json
{
  "name": "mark_invoice_sent",
  "description": "Mark an invoice as sent to the client",
  "parameters": {
    "type": "object",
    "properties": {
      "invoice_id": {
        "type": "string",
        "description": "ID of the invoice to mark as sent"
      }
    },
    "required": ["invoice_id"]
  }
}
```

## Usage Examples

### Natural Language Invoice Creation

Your LLM can now handle requests like:

- "Create an invoice for $150 for web design services for John Doe"
- "Invoice Sarah Smith $75 for consulting work, due next Friday"
- "Create a $200 invoice for project management services for client@example.com"

### Programmatic Usage

```python
from app.invoice_llm_processor import get_invoice_llm_processor

async def create_invoice_example():
    processor = await get_invoice_llm_processor()
    
    result = await processor.create_invoice(
        description="Web development services",
        amount=500.00,
        client_name="Acme Corp",
        client_email="billing@acme.com",
        due_date="2024-01-15"
    )
    
    if result["success"]:
        print(f"Invoice created: {result['invoice_id']}")
    else:
        print(f"Error: {result['message']}")
```

## Testing

Run the test script to verify the integration:

```bash
python test_invoice_integration.py
```

## Security Notes

- The API token is stored in the configuration
- All API calls are authenticated
- Input validation is performed on all parameters
- Error handling is implemented for all operations

## Next Steps

1. **Test the integration** using the test script
2. **Configure your LLM** to use the new function definitions
3. **Start creating invoices** through natural language prompts
4. **Monitor and manage** your invoices through the API endpoints

## Troubleshooting

### Common Issues

1. **Connection refused**: Ensure InvoiceNinja is running on port 9000
2. **Authentication failed**: Verify the API token is correct
3. **Client not found**: The system will automatically create new clients
4. **Invalid amount**: Ensure amounts are numeric values

### Debug Mode

Enable debug logging by setting the log level in your application configuration.

## Support

For issues with the integration, check:
1. InvoiceNinja API documentation
2. Application logs for detailed error messages
3. Network connectivity to the InvoiceNinja instance 