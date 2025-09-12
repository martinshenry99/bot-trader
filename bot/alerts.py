import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.notifier import send_message
from db.models import get_session, Alert
import time

logger = logging.getLogger("alerts")

async def send_alert(user_id, wallet_address, token_contract, tx_hash, action, amount_usd, message, buttons=None):
    session = get_session()
    alert = Alert(
        user_id=user_id,
        wallet_address=wallet_address,
        token_contract=token_contract,
        tx_hash=tx_hash,
        action=action,
        amount_usd=amount_usd,
        created_at=int(time.time())
    )
    session.add(alert)
    session.commit()
    await send_message(user_id, message, buttons)
    logger.info(f"WATCH_ALERT_SENT: {wallet_address} {action} {token_contract} {amount_usd}")

async def send_admin_alert(message):
    from os import getenv
    admin_id = int(getenv("ADMIN_TELEGRAM_ID", "639088027"))
    await send_message(admin_id, f"ALERT: {message}")
    logger.info(f"ADMIN_ALERT_SENT: {message}")
