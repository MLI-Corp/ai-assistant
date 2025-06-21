import email
import imaplib
import email.utils
from email.header import decode_header
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta
from .llm_processor import LLMProcessor
from .invoice_generator import InvoiceGenerator
from .config import settings

logger = logging.getLogger(__name__)

class EmailProcessor:
    def __init__(self):
        self.llm_processor = LLMProcessor()
        self.invoice_generator = InvoiceGenerator()
        self.processed_uids = set()
    
    def connect_to_email(self) -> Optional[imaplib.IMAP4_SSL]:
        """Connect to the email server"""
        try:
            mail = imaplib.IMAP4_SSL(settings.EMAIL_SERVER, settings.EMAIL_PORT)
            mail.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
            mail.select(settings.EMAIL_FOLDER)
            return mail
        except Exception as e:
            logger.error(f"Error connecting to email: {str(e)}")
            return None
    
    def get_email_content(self, msg: email.message.Message) -> Dict[str, Any]:
        """Extract content and metadata from an email"""
        email_data = {
            'subject': '',
            'from': '',
            'to': '',
            'date': '',
            'body': '',
            'attachments': []
        }
        
        # Decode email subject
        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding or 'utf-8', errors='ignore')
        email_data['subject'] = subject
        
        # Get sender and recipient
        email_data['from'] = msg.get("From")
        email_data['to'] = msg.get("To")
        email_data['date'] = msg.get("Date")
        
        # Extract email body and attachments
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            # Skip any text/plain (txt) or text/html (html) attachments
            if part.get_content_maintype() == "multipart" or part.get('Content-Disposition') is None:
                continue
                
            # Get the email body
            if part.get_content_type() == "text/plain" and "attachment" not in content_disposition:
                try:
                    body = part.get_payload(decode=True).decode('utf-8')
                    email_data['body'] = body
                except Exception as e:
                    logger.error(f"Error decoding email body: {str(e)}")
            
            # Handle attachments
            elif "attachment" in content_disposition:
                filename = part.get_filename()
                if filename:
                    try:
                        filename = decode_header(filename)[0][0]
                        if isinstance(filename, bytes):
                            filename = filename.decode('utf-8', errors='ignore')
                        file_data = part.get_payload(decode=True)
                        email_data['attachments'].append({
                            'filename': filename,
                            'data': file_data,
                            'content_type': content_type
                        })
                    except Exception as e:
                        logger.error(f"Error processing attachment: {str(e)}")
        
        return email_data
    
    async def search_emails(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search emails based on a query
        
        Args:
            query: Search query
            limit: Maximum number of results to return
            
        Returns:
            List of matching emails with basic info
        """
        mail = self.connect_to_email()
        if not mail:
            logger.error("Failed to connect to email server")
            return []
            
        try:
            # Search for emails matching the query
            status, messages = mail.search(None, 'TEXT', f'"{query}"')
            if status != 'OK':
                logger.error("Error searching emails")
                return []
                
            # Get the list of message IDs
            message_ids = messages[0].split()
            message_ids = message_ids[-limit:]  # Get most recent up to limit
            
            results = []
            for msg_id in message_ids:
                try:
                    # Fetch the email
                    status, msg_data = mail.fetch(msg_id, '(RFC822)')
                    if status != 'OK':
                        continue
                        
                    # Parse the email
                    email_message = email.message_from_bytes(msg_data[0][1])
                    
                    # Extract basic info
                    subject = email_message.get('Subject', 'No Subject')
                    from_ = email_message.get('From', 'Unknown Sender')
                    date = email_message.get('Date', '')
                    
                    results.append({
                        'id': msg_id.decode(),
                        'subject': subject,
                        'from': from_,
                        'date': date,
                        'snippet': self._get_email_snippet(email_message)
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing email {msg_id}: {str(e)}")
                    continue
                    
            return results
            
        except Exception as e:
            logger.error(f"Error in search_emails: {str(e)}")
            return []
        finally:
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except:
                    pass
    
    async def get_email(self, email_id: str) -> Dict[str, Any]:
        """
        Get details of a specific email by ID
        
        Args:
            email_id: The ID of the email to retrieve
            
        Returns:
            Dictionary containing the email details
        """
        mail = self.connect_to_email()
        if not mail:
            logger.error("Failed to connect to email server")
            return None
            
        try:
            # Fetch the email
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status != 'OK':
                logger.error(f"Failed to fetch email {email_id}")
                return None
                
            # Parse the email
            email_message = email.message_from_bytes(msg_data[0][1])
            
            # Extract email data
            email_data = self.get_email_content(email_message)
            email_data['id'] = email_id
            
            return email_data
            
        except Exception as e:
            logger.error(f"Error in get_email: {str(e)}")
            return None
        finally:
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except:
                    pass
    
    def _get_email_snippet(self, msg: email.message.Message, max_length: int = 200) -> str:
        """Extract a text snippet from an email"""
        try:
            # Try to get text/plain part first
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")).lower():
                    payload = part.get_payload(decode=True)
                    if payload:
                        text = payload.decode('utf-8', errors='ignore')
                        return (text[:max_length] + '...') if len(text) > max_length else text
            
            # If no text/plain part, try to get any text
            for part in msg.walk():
                if part.get_content_maintype() == "text" and "attachment" not in str(part.get("Content-Disposition", "")).lower():
                    payload = part.get_payload(decode=True)
                    if payload:
                        text = payload.decode('utf-8', errors='ignore')
                        return (text[:max_length] + '...') if len(text) > max_length else text
            
            return "No text content found"
        except Exception as e:
            logger.error(f"Error extracting email snippet: {str(e)}")
            return "Error extracting content"
    
    def process_emails(self) -> None:
        """Process new emails and create invoices"""
        mail = self.connect_to_email()
        if not mail:
            logger.error("Failed to connect to email server")
            return
        
        try:
            # Search for unread emails
            status, messages = mail.search(None, 'UNSEEN')
            if status != 'OK':
                logger.error("Error searching for emails")
                return
            
            # Get the list of email UIDs
            email_uids = messages[0].split()
            
            for uid in email_uids:
                if uid in self.processed_uids:
                    continue
                
                try:
                    # Fetch the email
                    status, msg_data = mail.fetch(uid, '(RFC822)')
                    if status != 'OK':
                        logger.error(f"Error fetching email UID {uid}")
                        continue
                    
                    # Parse the email
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    # Process the email
                    email_data = self.get_email_content(msg)
                    
                    # Use LLM to extract invoice information
                    invoice_data = self.llm_processor.process_email(
                        f"Subject: {email_data['subject']}\n\n{email_data['body']}"
                    )
                    
                    if not invoice_data:
                        logger.warning("No invoice data could be extracted from email")
                        continue
                    
                    # Ensure we have required fields
                    if 'client_email' not in invoice_data:
                        invoice_data['client_email'] = email_data['from']
                    
                    # Create the invoice
                    invoice = self.invoice_generator.create_invoice(invoice_data)
                    if not invoice:
                        logger.error("Failed to create invoice")
                        continue
                    
                    # Send the invoice email
                    self.invoice_generator.send_invoice_email(
                        invoice_id=invoice.get('id'),
                        email=invoice_data.get('client_email')
                    )
                    
                    # Mark as processed
                    self.processed_uids.add(uid)
                    logger.info(f"Successfully processed email and created invoice {invoice.get('number')}")
                    
                except Exception as e:
                    logger.error(f"Error processing email: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in email processing loop: {str(e)}")
            
        finally:
            try:
                mail.close()
                mail.logout()
            except:
                pass
