"""
Telegram alert handler for Meme Trader V4 Pro
"""
import os
import logging
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

async def send_telegram_alert(message: str) -> bool:
    """Send alert message via Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram configuration missing")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    return True
                else:
                    logger.error(f"Telegram API error: {response.status}")
                    return False
    except Exception as e:
        logger.error(f"Error sending Telegram alert: {e}")
        return False
