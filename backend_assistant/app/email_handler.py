import imaplib
import email
from email.header import decode_header
import logging
import time
import asyncio
from typing import Optional, Any

import aiohttp

from .config import settings
from .database import log_event
from .data_extractor import DataExtractor
from .invoiceninja_client import InvoiceNinjaClient
from .calendar_handler import GoogleCalendarHandler
from .notification_handler import WebhookNotificationHandler

# Placeholder for ConnectionManager type to avoid circular import if it's in main.py
# In a larger app, ConnectionManager might be in a common 'utils' or 'ws' module.
ConnectionType = Any # from main import ConnectionManager

logger = logging.getLogger(__name__)

class EmailHandler:
    def __init__(self, websocket_manager: ConnectionType):
        self.imap_host = settings.IMAP_HOST
        self.imap_port = settings.IMAP_PORT
        self.imap_user = settings.IMAP_USER
        self.imap_password = settings.IMAP_PASSWORD
        self.poll_interval = settings.EMAIL_POLL_INTERVAL
        self.websocket_manager = websocket_manager

        self.mail: Optional[imaplib.IMAP4] = None
        self._stop_event = asyncio.Event()
        self._http_session: Optional[aiohttp.ClientSession] = None

        self.data_extractor: Optional[DataExtractor] = None
        self.invoice_ninja_client: Optional[InvoiceNinjaClient] = None
        self.calendar_handler: Optional[GoogleCalendarHandler] = None
        self.notification_handler: Optional[WebhookNotificationHandler] = None

    async def _broadcast_ws(self, message: str):
        if self.websocket_manager:
            await self.websocket_manager.broadcast(message)

    async def _get_or_create_http_session(self) -> aiohttp.ClientSession:
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
            logger.info("Shared aiohttp.ClientSession created.")
            await self._broadcast_ws("DEBUG: HTTP session created.")
        return self._http_session

    async def _ensure_clients_initialized(self):
        session = await self._get_or_create_http_session()
        if self.data_extractor is None:
            self.data_extractor = DataExtractor(session=session)
            logger.info("DataExtractor initialized.")
        if self.invoice_ninja_client is None:
            self.invoice_ninja_client = InvoiceNinjaClient(session=session)
            logger.info("InvoiceNinjaClient initialized.")
        if self.calendar_handler is None and settings.GOOGLE_CLIENT_ID:
            self.calendar_handler = GoogleCalendarHandler()
            logger.info("GoogleCalendarHandler initialized.")
        if self.notification_handler is None and settings.NOTIFICATION_WEBHOOK_URL:
            self.notification_handler = WebhookNotificationHandler(session=session)
            logger.info("WebhookNotificationHandler initialized.")

    async def _close_http_session(self):
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            logger.info("Shared aiohttp.ClientSession closed.")
            await self._broadcast_ws("DEBUG: HTTP session closed.")
            self._http_session = None

    def _connect(self): # Synchronous
        try:
            logger.info(f"Connecting to IMAP: {self.imap_host}")
            # await self._broadcast_ws(f"INFO: Connecting to IMAP server {self.imap_host}...") # Cannot await in sync
            if self.imap_port == 993:
                self.mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            else:
                self.mail = imaplib.IMAP4(self.imap_host, self.imap_port)
            login_status, _ = self.mail.login(self.imap_user, self.imap_password)
            if login_status == 'OK':
                logger.info("IMAP login successful.")
                log_event("IMAP_CONNECT_SUCCESS", f"IMAP login success for {self.imap_user}")
                # await self._broadcast_ws("INFO: IMAP login successful.") # Cannot await
                return True
            else:
                logger.error(f"IMAP login failed.")
                log_event("IMAP_CONNECT_FAIL", f"IMAP login failed for {self.imap_user}")
                # await self._broadcast_ws("ERROR: IMAP login failed.") # Cannot await
                self.mail = None
                return False
        except Exception as e:
            logger.error(f"IMAP connection error: {e}", exc_info=True)
            log_event("IMAP_CONNECT_ERROR", f"IMAP connection error: {e}")
            # if self.websocket_manager: asyncio.create_task(self.websocket_manager.broadcast(f"ERROR: IMAP connection error: {e}"))
            self.mail = None
            return False

    def _disconnect(self): # Synchronous
        if self.mail:
            try:
                # await self._broadcast_ws("INFO: Disconnecting from IMAP...") # Cannot await
                self.mail.close()
                self.mail.logout()
                logger.info("IMAP connection closed.")
            except Exception as e:
                logger.warning(f"Error during IMAP logout/close: {e}")
            finally:
                self.mail = None

    def _decode_header(self, header_value: str) -> str:
        if not header_value: return ""
        decoded_parts = []
        for bytes_part, charset in decode_header(header_value):
            if isinstance(bytes_part, bytes):
                decoded_parts.append(bytes_part.decode(charset or 'utf-8', errors='replace'))
            else:
                decoded_parts.append(bytes_part)
        return "".join(decoded_parts)

    def _parse_email_message(self, msg_data):
        # ... (parsing logic remains the same, ensure no await calls) ...
        if isinstance(msg_data, tuple): msg_data = msg_data[1]
        if not isinstance(msg_data, bytes): return None
        msg = email.message_from_bytes(msg_data)
        email_info = {
            "subject": self._decode_header(msg.get("Subject")),
            "from": self._decode_header(msg.get("From")), "to": self._decode_header(msg.get("To")),
            "date": self._decode_header(msg.get("Date")), "message_id": msg.get("Message-ID"),
            "body_text": "", "body_html": "", "attachments": []
        }
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if "attachment" not in content_disposition:
                    if content_type == "text/plain":
                        try: email_info["body_text"] += part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                        except: pass
                    elif content_type == "text/html":
                        try: email_info["body_html"] += part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                        except: pass
                else:
                    filename = part.get_filename()
                    if filename: email_info["attachments"].append(self._decode_header(filename))
        else:
            content_type = msg.get_content_type()
            if content_type == "text/plain":
                try: email_info["body_text"] = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='replace')
                except: pass
            elif content_type == "text/html":
                try: email_info["body_html"] = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='replace')
                except: pass
        return email_info


    async def fetch_new_emails(self, mailbox="inbox", criteria="UNSEEN"):
        # ... (fetch logic largely same, ensure no await calls to websocket_manager directly from sync parts) ...
        if not self.mail:
            if not self._connect(): return [] # _connect is sync

        emails_data = []
        try:
            status, _ = self.mail.select(mailbox) # select is sync
            if status != 'OK':
                logger.error(f"Failed to select mailbox '{mailbox}'.")
                self._disconnect()
                return []

            status, messages = self.mail.search(None, criteria) # search is sync
            if status != 'OK': return []

            email_ids = messages[0].split()
            if not email_ids: return []

            logger.info(f"Found {len(email_ids)} new email(s).")
            await self._broadcast_ws(f"INFO: Found {len(email_ids)} new email(s) matching '{criteria}'.")


            for email_id_bytes in email_ids:
                # Fetch is sync
                status, msg_data_parts = self.mail.fetch(email_id_bytes, "(RFC822)")
                if status == 'OK':
                    for part in msg_data_parts:
                        if isinstance(part, tuple):
                            parsed_email = self._parse_email_message(part[1]) # parse is sync
                            if parsed_email:
                                parsed_email['uid'] = email_id_bytes.decode()
                                emails_data.append(parsed_email)
                else:
                    logger.error(f"Failed to fetch email ID {email_id_bytes.decode()}.")
            return emails_data
        except Exception as e:
            logger.error(f"Error fetching emails: {e}", exc_info=True)
            self._disconnect() # Ensure disconnect on error
            return []


    async def archive_email(self, email_uid: str, archive_folder: str = "Processed", source_mailbox: str = "inbox"):
        # ... (archive logic largely same, ensure no await calls to websocket_manager directly from sync parts) ...
        if not self.mail:
            if not self._connect(): return False
        try:
            self.mail.select(source_mailbox)
            # Create folder if not exists (simplified check)
            self.mail.create(archive_folder) # Ignores error if already exists usually

            copy_status, _ = self.mail.uid('copy', email_uid, archive_folder)
            if copy_status != 'OK': return False

            self.mail.uid('store', email_uid, '+FLAGS', '\\Deleted')
            self.mail.expunge()
            logger.info(f"Email UID {email_uid} archived to '{archive_folder}'.")
            await self._broadcast_ws(f"INFO: Email UID {email_uid} archived to '{archive_folder}'.")
            return True
        except Exception as e:
            logger.error(f"Error archiving email UID {email_uid}: {e}", exc_info=True)
            self._disconnect()
            return False

    async def monitor_emails(self):
        logger.info("Starting email monitoring polling loop...")
        await self._broadcast_ws("INFO: Email monitoring loop started.")
        await self._ensure_clients_initialized()

        if not self._connect():
            logger.error("Initial IMAP connection failed. Monitoring will attempt reconnections.")
            await self._broadcast_ws("ERROR: Initial IMAP connection failed.")
            await asyncio.sleep(self.poll_interval / 2 if self.poll_interval > 4 else 2)

        while not self._stop_event.is_set():
            try:
                if not self.mail or not self.mail.sock:
                    logger.warning("IMAP connection lost. Reconnecting...")
                    await self._broadcast_ws("WARNING: IMAP connection lost. Attempting to reconnect...")
                    if not self._connect():
                        logger.error("IMAP reconnect failed.")
                        await self._broadcast_ws("ERROR: IMAP reconnection failed. Retrying after interval.")
                        await asyncio.sleep(self.poll_interval)
                        continue

                await self._ensure_clients_initialized() # Ensure HTTP clients are ready
                if not self.data_extractor: # Critical component
                    logger.error("DataExtractor not initialized. Skipping poll cycle.")
                    await self._broadcast_ws("ERROR: DataExtractor not available. Processing stalled.")
                    await asyncio.sleep(self.poll_interval)
                    continue

                logger.debug("Polling for new emails...")
                await self._broadcast_ws("INFO: Polling for new emails...")
                new_emails = await self.fetch_new_emails()

                if new_emails:
                    for email_content in new_emails:
                        subject_preview = email_content.get('subject','N/A')[:50]
                        await self._broadcast_ws(f"INFO: Processing email - Subject: {subject_preview}...")

                        extracted_data = await self.data_extractor.process_email_content(email_content)

                        if extracted_data:
                            auth_id = extracted_data.get('authorization_id', 'N/A')
                            await self._broadcast_ws(f"INFO: Data extracted for Auth ID {auth_id}.")

                            if self.invoice_ninja_client:
                                inv_id = await self.invoice_ninja_client.create_invoice(extracted_data)
                                if inv_id: extracted_data['invoice_id'] = inv_id; await self._broadcast_ws(f"SUCCESS: Invoice {inv_id} created for Auth ID {auth_id}.")
                                else: await self._broadcast_ws(f"ERROR: Failed to create invoice for Auth ID {auth_id}.")

                            if self.calendar_handler and extracted_data.get("service_datetime_obj_cst"):
                                cal_id = await self.calendar_handler.create_event(extracted_data)
                                if cal_id: extracted_data['calendar_event_id'] = cal_id; await self._broadcast_ws(f"SUCCESS: Calendar event {cal_id} created for Auth ID {auth_id}.")
                                elif not extracted_data.get("service_date_is_past"): await self._broadcast_ws(f"WARNING: Calendar event creation failed/skipped for Auth ID {auth_id}.")

                            if self.notification_handler: # Webhook notification
                                await self.notification_handler.send_processing_summary(extracted_data)
                                # The notification handler already logs to DB, so summary is captured.
                                # We can also broadcast the same summary message via WebSocket if desired.
                                summary_msg_for_ws = self.notification_handler.construct_summary_message(extracted_data) # Assume such a helper
                                await self._broadcast_ws(f"SUMMARY [AuthID {auth_id}]: {summary_msg_for_ws}")


                            await self.archive_email(email_content['uid'], "Processed")
                        else: # No relevant data extracted
                            msg = f"Email (Subject: {subject_preview}) not actionable or data extraction failed."
                            await self._broadcast_ws(f"INFO: {msg}")
                            if self.data_extractor and self.data_extractor.is_authorization_email(email_content):
                                await self.archive_email(email_content['uid'], "FailedProcessing")
                            if self.notification_handler:
                                await self.notification_handler.send_processing_summary(
                                    {"original_email_subject": subject_preview, "uid": email_content.get("uid")},
                                    error_message="Not actionable or data extraction failed."
                                )
                else:
                    logger.debug("No new emails found.")
                    await self._broadcast_ws("INFO: No new emails found in this poll.")

                await asyncio.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("KeyboardInterrupt! Stopping monitor.")
                await self._broadcast_ws("WARNING: Email monitor stopping (KeyboardInterrupt).")
                break
            except Exception as e:
                logger.error(f"Unhandled exception in monitor_emails: {e}", exc_info=True)
                await self._broadcast_ws(f"CRITICAL_ERROR: Unhandled exception in email monitor: {e}")
                await asyncio.sleep(self.poll_interval * 2) # Longer pause after critical error

        await self.stop_monitoring() # Ensure cleanup if loop exits

    async def start_monitoring(self):
        self._stop_event.clear()
        logger.info("Scheduling email monitoring.")
        await self._ensure_clients_initialized() # Ensure all clients are ready
        asyncio.create_task(self.monitor_emails())
        # Startup broadcast is now at the beginning of monitor_emails

    async def stop_monitoring(self):
        logger.info("Attempting to stop email monitoring...")
        await self._broadcast_ws("INFO: Email monitoring service stopping...")
        self._stop_event.set()
        await self._close_http_session()
        self._disconnect() # Close IMAP connection
        logger.info("Email monitoring stopped.")
        await self._broadcast_ws("INFO: Email monitoring service has stopped.")

# Note: The main_test() function would need significant updates
# to mock/provide the websocket_manager. Removed for brevity in this overwrite.
# If direct testing of EmailHandler is needed, it should be refactored.
