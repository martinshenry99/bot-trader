import logging
import asyncio
from telegram import Bot
from telegram.error import TelegramError
import os

logger = logging.getLogger("notifier")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

class Notifier:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.last_sent = {}
        self.rate_limit = 1  # seconds

    async def send_message(self, user_id, text, buttons=None):
        now = asyncio.get_event_loop().time()
        last = self.last_sent.get(user_id, 0)
        if now - last < self.rate_limit:
            await asyncio.sleep(self.rate_limit - (now - last))
        self.last_sent[user_id] = now
        try:
            if buttons:
                await self.bot.send_message(chat_id=user_id, text=text, reply_markup=buttons, parse_mode="Markdown")
            else:
                await self.bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
        except TelegramError as e:
            logger.error(f"Notifier error: {e}")

notifier = Notifier()
async def send_message(user_id, text, buttons=None):
    await notifier.send_message(user_id, text, buttons)
