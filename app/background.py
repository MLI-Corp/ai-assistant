import asyncio
import logging
import time
from typing import Optional

from .email_processor import EmailProcessor
from .config import settings

logger = logging.getLogger(__name__)

class BackgroundMonitor:
    def __init__(self):
        self.is_running = False
        self.email_processor = EmailProcessor()
        self.check_interval = settings.EMAIL_CHECK_INTERVAL  # in seconds
        
    async def start(self):
        """Start the background email monitoring service"""
        if self.is_running:
            logger.info("Background monitor is already running")
            return
            
        self.is_running = True
        logger.info("Starting background email monitoring service")
        
        while self.is_running:
            try:
                # Process emails
                self.email_processor.process_emails()
                
                # Wait for the next check interval
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in background email monitoring: {str(e)}", exc_info=True)
                # Wait before retrying after an error
                await asyncio.sleep(min(60, self.check_interval))
    
    def stop(self):
        """Stop the background email monitoring service"""
        logger.info("Stopping background email monitoring service")
        self.is_running = False

# Global instance of the background monitor
background_monitor = BackgroundMonitor()

async def start_background_tasks():
    """Start background tasks when the application starts"""
    if settings.ENABLE_EMAIL_MONITORING:
        asyncio.create_task(background_monitor.start())

async def stop_background_tasks():
    """Stop background tasks when the application shuts down"""
    if settings.ENABLE_EMAIL_MONITORING:
        background_monitor.stop()
