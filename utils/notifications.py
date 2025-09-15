import logging
from typing import Optional

logger = logging.getLogger(__name__)

async def send_alert(title: str, message: str, severity: Optional[str] = "info"):
    """Send notification to configured channels"""
    try:
        # Log the alert
        log_level = logging.WARNING if severity == "warning" else logging.INFO
        logger.log(log_level, f"{title}: {message}")
        
        # TODO: Implement additional notification channels (Telegram, Discord, etc.)
        
    except Exception as e:
        logger.error(f"Failed to send alert: {str(e)}")
