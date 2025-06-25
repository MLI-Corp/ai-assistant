import logging
import json
from typing import Dict, Any, Optional, List
import aiohttp

from .config import settings
from .database import log_event

logger = logging.getLogger(__name__)

class InvoiceNinjaClient:
    def __init__(self, session: aiohttp.ClientSession):
        self.api_url = settings.INVOICENINJA_URL.rstrip('/') + "/api/v1"
        self.api_token = settings.INVOICENINJA_API_TOKEN
        self.session = session # Use a shared session if possible
from .utils import retry_async # Import the retry decorator

        self.headers = {
            "X-API-Token": self.api_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @retry_async(attempts=3, delay_seconds=2)
    async def _request(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        # The try-except for ClientError and general Exception is now handled by the decorator mostly.
        # However, specific handling for non-2xx responses should remain inside.

        async with self.session.request(method, url, json=data, params=params, headers=self.headers) as response:
            response_text = await response.text() # Read text first for logging in all cases
            logger.debug(f"InvoiceNinja API Request: {method} {url} | Status: {response.status} | Response: {response_text[:200]}...")

            if 200 <= response.status < 300:
                try:
                    # Attempt to parse JSON only if successful
                    return json.loads(response_text) # Use json.loads for potentially empty responses
                except json.JSONDecodeError:
                    logger.warning(f"InvoiceNinja API returned non-JSON response for {method} {url} with status {response.status} but successful. Raw: {response_text[:200]}")
                    # If IN sometimes returns empty body on success (e.g. 204 No Content), handle it
                    if not response_text.strip() and response.status in [200, 201, 204]:
                         return {"status": "success", "message": f"Request to {endpoint} successful with status {response.status}, empty body."}
                    return {"raw_response": response_text} # Or handle as error
            else:
                # This is an API error (4xx, 5xx), not a client connection error.
                # The retry decorator might retry this if raise_for_status() was used,
                # but here we are checking status manually.
                # For InvoiceNinja, we might not want to retry all 4xx errors (e.g. 404 Not Found).
                # The current retry decorator retries ANY exception.
                # Consider a more specific exception type for retrying if needed, or adjust decorator.
                logger.error(f"InvoiceNinja API Error: {method} {url} | Status: {response.status} | Response: {response_text}")
                log_event(
                    "INVOICENINJA_API_ERROR",
                    f"Status: {response.status}, Endpoint: {endpoint}, Method: {method}",
                    details=response_text[:1000]
                )
                # To make it retry on these, we'd need to raise an exception here that the decorator catches.
                # For now, it will return None and not retry these non-2xx status codes unless session.request itself fails.
                # If we want to retry 5xx errors from InvoiceNinja:
                # if response.status >= 500:
                #    response.raise_for_status() # This will raise an ClientResponseError for retry decorator
                return None


    async def get_client_by_email(self, email: str) -> Optional[str]:
        """Retrieves a client ID by email address."""
        params = {"email": email}
        response_data = await self._request("GET", "clients", params=params)
        if response_data and "data" in response_data and len(response_data["data"]) > 0:
            client_id = response_data["data"][0].get("id")
            logger.info(f"Found client ID '{client_id}' for email '{email}'.")
            return str(client_id)
        logger.info(f"No client found for email '{email}'.")
        return None

    async def create_client(self, name: str, email: str) -> Optional[str]:
        """Creates a new client and returns their ID."""
        # Basic client payload, might need more fields depending on IN setup
        payload = {
            "name": name,
            # InvoiceNinja typically uses 'contacts' array for email, phone etc.
            "contacts": [
                {
                    "email": email,
                    "is_primary": True,
                    # "first_name": name.split(" ")[0] if name else "", # Basic split
                    # "last_name": " ".join(name.split(" ")[1:]) if name and " " in name else "",
                }
            ]
            # Add other fields like address if available and needed
        }
        logger.info(f"Attempting to create client: Name='{name}', Email='{email}'")
        response_data = await self._request("POST", "clients", data=payload)
        if response_data and "data" in response_data:
            client_id = response_data["data"].get("id")
            logger.info(f"Successfully created client Name='{name}', Email='{email}', ID='{client_id}'.")
            log_event("INVOICENINJA_CLIENT_CREATED", f"Client {name} ({email}) created with ID {client_id}")
            return str(client_id)
        logger.error(f"Failed to create client Name='{name}', Email='{email}'. Response: {response_data}")
        log_event("INVOICENINJA_CLIENT_CREATE_FAIL", f"Failed to create client {name} ({email})")
        return None

    async def create_invoice(self, extracted_data: Dict[str, Any]) -> Optional[str]:
        """
        Creates an invoice in InvoiceNinja based on extracted email data.
        Returns the ID of the created invoice, or None on failure.
        """
        client_email = extracted_data.get("client_email")
        client_name = extracted_data.get("client_name", "Unknown Client") # Fallback name
        auth_id = extracted_data.get("authorization_id", "N/A")

        if not client_email:
            logger.error("Cannot create invoice: client_email is missing from extracted_data.")
            log_event("INVOICE_CREATE_FAIL", "Missing client_email", f"AuthID: {auth_id}")
            return None

        client_id = await self.get_client_by_email(client_email)
        if not client_id:
            logger.info(f"Client with email '{client_email}' not found. Attempting to create.")
            client_id = await self.create_client(name=client_name, email=client_email)
            if not client_id:
                logger.error(f"Failed to find or create client for email '{client_email}'. Cannot create invoice.")
                log_event("INVOICE_CREATE_FAIL", "Client find/create failed", f"Email: {client_email}, AuthID: {auth_id}")
                return None

        # Construct line items
        line_items = []
        service_description = f"Services for Authorization ID: {auth_id}"
        if extracted_data.get("patient_name"):
            service_description += f" (Patient: {extracted_data.get('patient_name')})"

        # For now, assume a single line item for the service.
        # This needs to be more dynamic based on actual services/rates.
        # Using a placeholder product_key and notes for now.
        # The actual amount/rate would come from client_billing_rates or be fixed.
        # This part is highly dependent on how billing is structured.

        # Placeholder: Assume a flat rate or a primary service item.
        # A real implementation would fetch rates from config (e.g., settings.CLIENT_BILLING_RATES_PATH)
        # or have more structured product/service management.
        item_cost = 100.00 # Placeholder cost
        item_qty = 1       # Placeholder quantity

        line_items.append({
            "product_key": extracted_data.get("patient_name", "Service") if extracted_data.get("patient_name") else "General Service", # Or a more generic service key
            "notes": service_description,
            "cost": item_cost,
            "quantity": item_qty,
            # "custom_value1": auth_id, # If custom fields are used for Auth ID
        })

        # Add mileage as a separate line item if present
        mileage = extracted_data.get("mileage_extracted") or extracted_data.get("mileage_calculated")
        if mileage and mileage > 0:
            # Get mileage rate (example, needs to be loaded from config for the client)
            # mileage_rate = settings.get_client_rate(client_email, "mileage_rate") or 0.50 # fallback
            mileage_rate = 0.50 # Placeholder, fetch from DataExtractor.get_client_rate()

            # Retrieve mileage rate from data_extractor instance (passed or accessed globally, needs refactor)
            # For now, using placeholder. DataExtractor instance isn't directly available here.
            # This indicates a need to pass data_extractor or its rates to this client, or have client load them.
            # Let's assume data_extractor has already put 'calculated_mileage_cost' or similar if applicable.

            line_items.append({
                "product_key": "Mileage", # Ensure "Mileage" is a product/service in InvoiceNinja
                "notes": f"Travel mileage for Auth ID: {auth_id}",
                "cost": mileage_rate, # Cost per mile
                "quantity": mileage,   # Number of miles
            })

        if not line_items:
            logger.error("No line items to add to invoice. Cannot create invoice.")
            log_event("INVOICE_CREATE_FAIL", "No line items", f"AuthID: {auth_id}")
            return None

        invoice_payload = {
            "client_id": client_id,
            "line_items": line_items,
            "public_notes": f"Authorization ID: {auth_id}\nService Date: {extracted_data.get('service_date_cst_iso', 'N/A')}",
            # "due_date": "YYYY-MM-DD" # Optional, can be set based on service_date_cst
            # "status_id": "1", # 1 for Draft, 2 for Sent, etc. Default is usually Draft.
            # "auto_bill": "true" / "false" or specific settings
        }

        if extracted_data.get("service_date_cst_iso"):
            # Set invoice date to service date if available
            invoice_payload["date"] = extracted_data.get("service_date_cst_iso").split("T")[0]
            # Optionally set due_date, e.g., 30 days from service date
            # from datetime import datetime, timedelta
            # service_dt = datetime.fromisoformat(extracted_data.get("service_date_cst_iso"))
            # invoice_payload["due_date"] = (service_dt + timedelta(days=30)).strftime('%Y-%m-%d')


        logger.info(f"Attempting to create invoice for Client ID '{client_id}', Auth ID '{auth_id}'.")
        response_data = await self._request("POST", "invoices", data=invoice_payload)

        if response_data and "data" in response_data:
            invoice_id = response_data["data"].get("id")
            invoice_number = response_data["data"].get("number")
            logger.info(f"Successfully created invoice ID '{invoice_id}' (Number: {invoice_number}) for Auth ID '{auth_id}'.")
            log_event("INVOICE_CREATED", f"Invoice {invoice_number} (ID: {invoice_id}) created for AuthID {auth_id}, ClientID {client_id}")
            return str(invoice_id)

        logger.error(f"Failed to create invoice for Auth ID '{auth_id}'. Response: {response_data}")
        log_event("INVOICE_CREATE_FAIL", f"API call failed for AuthID {auth_id}", json.dumps(invoice_payload) if invoice_payload else "No payload")
        return None


# Example Usage (for standalone testing if needed)
async def test_invoice_ninja_client():
    logging.basicConfig(level=logging.DEBUG)
    # Ensure .env.assistant is loaded or variables are set
    # from dotenv import load_dotenv
    # load_dotenv('./backend_assistant/.env.assistant') # Adjust path as needed
    # global settings
    # settings = settings.__class__()


    async with aiohttp.ClientSession(headers={"User-Agent": "Test InvoiceNinjaClient"}) as session:
        client = InvoiceNinjaClient(session=session)

        # Test: Get client by email (use an email you know exists or doesn't)
        # existing_client_email = "testclient@example.com"
        # client_id = await client.get_client_by_email(existing_client_email)
        # if client_id:
        #     print(f"Found client ID for {existing_client_email}: {client_id}")
        # else:
        #     print(f"Client {existing_client_email} not found. Creating one...")
        #     new_client_id = await client.create_client(name="Test Client New", email=existing_client_email)
        #     if new_client_id:
        #         print(f"Created new client with ID: {new_client_id}")
        #     else:
        #         print(f"Failed to create client {existing_client_email}")

        # Test: Create Invoice
        sample_extracted_data = {
            "authorization_id": "TESTAUTH123",
            "client_name": "Test Customer From Script",
            "client_email": "customer.script@example.com", # Change for each run or use a testable email
            "service_date_cst_iso": "2024-07-20T14:30:00-05:00",
            "mileage_extracted": 15.5,
            "patient_name": "Test Patient"
            # "service_location_address": "123 Test St"
        }

        # Create a new client first for the test invoice (or ensure one exists)
        test_client_id = await client.get_client_by_email(sample_extracted_data["client_email"])
        if not test_client_id:
             test_client_id = await client.create_client(
                 name=sample_extracted_data["client_name"],
                 email=sample_extracted_data["client_email"]
            )

        if test_client_id:
            print(f"Using client ID {test_client_id} for invoice creation test.")
            invoice_id = await client.create_invoice(sample_extracted_data)
            if invoice_id:
                print(f"Successfully created test invoice with ID: {invoice_id}")
            else:
                print("Failed to create test invoice.")
        else:
            print(f"Failed to get/create client for {sample_extracted_data['client_email']}, skipping invoice creation test.")


if __name__ == "__main__":
    # python -m backend_assistant.app.invoiceninja_client
    # Ensure InvoiceNinja is running and accessible, and .env.assistant has correct INVOICENINJA_URL and TOKEN
    asyncio.run(test_invoice_ninja_client())
