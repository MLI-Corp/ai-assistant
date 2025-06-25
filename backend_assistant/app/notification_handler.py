import logging
import json
from typing import Dict, Any, Optional

import aiohttp

from .config import settings
from .database import log_event

logger = logging.getLogger(__name__)

class WebhookNotificationHandler:
    def __init__(self, session: aiohttp.ClientSession):
        self.webhook_url = settings.NOTIFICATION_WEBHOOK_URL
        self.session = session

    async def send_notification(self, title: str, message: str, details: Optional[Dict[str, Any]] = None, success: bool = True):
        """
        Sends a notification to the configured webhook URL.

        Args:
            title: The main title/summary of the notification.
            message: A more detailed message.
            details: An optional dictionary for structured data (e.g., IDs, links).
            success: Boolean indicating if the operation being notified about was successful.
        """
        if not self.webhook_url:
            logger.warning("NOTIFICATION_WEBHOOK_URL not configured. Skipping notification.")
            return

        payload = {
            "title": title,
            "message": message,
            "success": success,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z", # ISO 8601 UTC
        }
        if details:
            payload["details"] = details

from .utils import retry_async # Import the retry decorator

        @retry_async(attempts=3, delay_seconds=5) # Webhooks can sometimes be slow/flaky
        async def _do_send():
            logger.info(f"Sending notification to webhook URL: {self.webhook_url}")
            # log_event("NOTIFICATION_SEND_ATTEMPT", title, json.dumps(payload) if payload else None) # Moved to after attempt

            async with self.session.post(self.webhook_url, json=payload) as response:
                response_text = await response.text()
                db_log_details = {"webhook_url": self.webhook_url, "payload_title": title, "status_code": response.status, "response_preview": response_text[:200]}
                if 200 <= response.status < 300:
                    logger.info(f"Webhook notification sent successfully. Status: {response.status}. Response: {response_text[:100]}")
                    log_event("NOTIFICATION_SENT", message, json.dumps(db_log_details))
                else:
                    logger.error(f"Failed to send webhook notification. Status: {response.status}. Response: {response_text}")
                    log_event("NOTIFICATION_FAIL", message, json.dumps(db_log_details))
                    # To make retry work for non-2xx, we should raise an error for >= 500
                    if response.status >= 500:
                        response.raise_for_status() # Will trigger retry by decorator

        try:
            await _do_send()
        except Exception as e: # Catch exceptions from _do_send (including after retries)
            logger.error(f"Failed to send webhook notification after retries to {self.webhook_url}: {e}", exc_info=True)
            # Log final failure, specific error type might be in e
            log_event("NOTIFICATION_FINAL_FAIL", title, json.dumps({"webhook_url": self.webhook_url, "error": str(e), "payload_title": title}))


    async def send_processing_summary(self, extracted_data: Dict[str, Any], error_message: Optional[str] = None):
        """
        Sends a standardized summary notification after processing an email.
        """
        auth_id = extracted_data.get("authorization_id", "N/A")
        subject = extracted_data.get("original_email_subject", "N/A")

        if error_message:
            title = f"Error Processing Email for Auth ID: {auth_id}"
            message = f"Failed to fully process email (Subject: {subject}). Error: {error_message}"
            success = False
            details = {
                "authorization_id": auth_id,
                "email_subject": subject,
                "error": error_message
            }
        else:
            title = f"Email Processed Successfully for Auth ID: {auth_id}"
            invoice_id = extracted_data.get("invoice_id")
            calendar_event_id = extracted_data.get("calendar_event_id")

            summary_parts = [f"Email (Subject: {subject}) processed."]
            if invoice_id:
                summary_parts.append(f"Invoice {invoice_id} created.")
            if calendar_event_id:
                summary_parts.append(f"Calendar event {calendar_event_id} created.")

            message = " ".join(summary_parts)
            if not invoice_id and not calendar_event_id and not extracted_data.get("service_date_is_past"): # if nothing was done but no error
                 message = f"Email (Subject: {subject}) processed for Auth ID: {auth_id}. No actions taken (e.g. service date past, or already processed)."


            success = True
            details = {
                "authorization_id": auth_id,
                "email_subject": subject,
                "client_name": extracted_data.get("client_name"),
                "client_email": extracted_data.get("client_email"),
                "service_date_cst": extracted_data.get("service_date_cst_iso"),
                "invoice_id": invoice_id,
                "calendar_event_id": calendar_event_id,
                "mileage_extracted": extracted_data.get("mileage_extracted"),
                "mileage_calculated": extracted_data.get("mileage_calculated")
            }

        await self.send_notification(title, message, details, success)


# Need to import datetime for the timestamp
import datetime

if __name__ == '__main__':
    # Example test (requires a webhook receiver like Beeceptor or a local test server)
    async def test_webhook_notifications():
        logging.basicConfig(level=logging.INFO)
        # Ensure .env.assistant is loaded or variables are set for NOTIFICATION_WEBHOOK_URL
        # from dotenv import load_dotenv
        # load_dotenv('./backend_assistant/.env.assistant') # Adjust path
        # global settings
        # settings = settings.__class__()

        if not settings.NOTIFICATION_WEBHOOK_URL:
            print("NOTIFICATION_WEBHOOK_URL not set. Skipping test.")
            return

        print(f"Test Webhook URL: {settings.NOTIFICATION_WEBHOOK_URL}")

        async with aiohttp.ClientSession() as session:
            handler = WebhookNotificationHandler(session=session)

            # Test success notification
            await handler.send_notification(
                title="Test Success Notification",
                message="This is a successful test message from the assistant.",
                details={"item_id": 123, "status": "COMPLETED"},
                success=True
            )

            # Test error notification
            await handler.send_notification(
                title="Test Error Notification",
                message="This is an error test message from the assistant.",
                details={"error_code": 500, "reason": "Simulated failure"},
                success=False
            )

            # Test processing summary
            sample_data = {
                "authorization_id": "SUMTEST001",
                "original_email_subject": "Test Email for Summary",
                "client_name": "Summary Client",
                "client_email": "summary@example.com",
                "service_date_cst_iso": datetime.datetime.now().isoformat(),
                "invoice_id": "INV-2024-001",
                "calendar_event_id": "calEventXYZ123"
            }
            await handler.send_processing_summary(sample_data)

            sample_error_data = {
                "authorization_id": "ERRSUM002",
                "original_email_subject": "Test Email for Error Summary",
            }
            await handler.send_processing_summary(sample_error_data, error_message="Failed to connect to external service.")


    # asyncio.run(test_webhook_notifications())
    print("WebhookNotificationHandler created. Run test_webhook_notifications() manually if configured.")
