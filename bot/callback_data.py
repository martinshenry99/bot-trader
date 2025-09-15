"""
Standardized callback data formats for Telegram inline buttons
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class CallbackFormat:
    # Analysis callbacks
    ANALYZE_WALLET = "analyze:wallet:{chain}:{address}"
    ANALYZE_TOKEN = "analyze:token:{chain}:{contract}"
    
    # Trading callbacks
    BUY_PREVIEW = "buy:preview:{chain}:{contract}:{usd_amount}"
    BUY_CONFIRM = "buy:confirm:{nonce}"
    SELL_PERCENT = "sell:percent:{contract}:{percentage}"
    SELL_CONFIRM = "sell:confirm:{nonce}"
    
    # Watchlist callbacks
    WATCHLIST_ADD = "watchlist:add:{chain}:{address}"
    WATCHLIST_REMOVE = "watchlist:remove:{address}"
    WATCHLIST_RENAME = "watchlist:rename:{address}"
    
    # Settings callbacks
    SETTINGS_SET = "settings:set:{key}:{value}"
    SETTINGS_RESET = "settings:reset"
    
    # Mnemonic callbacks (admin only)
    MNEMONIC_GENERATE = "mnemonic:generate"
    MNEMONIC_IMPORT = "mnemonic:import"
    MNEMONIC_EXPORT = "mnemonic:export"
    MNEMONIC_ROTATE = "mnemonic:rotate"
    MNEMONIC_DELETE = "mnemonic:delete"
    
    # Navigation callbacks
    BACK_TO_MENU = "nav:menu"
    REFRESH = "nav:refresh"
    PAGE = "nav:page:{number}"

def create_analyze_wallet_callback(chain: str, address: str) -> str:
    return CallbackFormat.ANALYZE_WALLET.format(chain=chain, address=address)

def create_analyze_token_callback(chain: str, contract: str) -> str:
    return CallbackFormat.ANALYZE_TOKEN.format(chain=chain, contract=contract)

def create_buy_preview_callback(chain: str, contract: str, usd_amount: float) -> str:
    return CallbackFormat.BUY_PREVIEW.format(chain=chain, contract=contract, usd_amount=usd_amount)

def create_buy_confirm_callback(nonce: str) -> str:
    return CallbackFormat.BUY_CONFIRM.format(nonce=nonce)

def create_sell_percent_callback(contract: str, percentage: int) -> str:
    return CallbackFormat.SELL_PERCENT.format(contract=contract, percentage=percentage)

def create_sell_confirm_callback(nonce: str) -> str:
    return CallbackFormat.SELL_CONFIRM.format(nonce=nonce)

def create_watchlist_add_callback(chain: str, address: str) -> str:
    return CallbackFormat.WATCHLIST_ADD.format(chain=chain, address=address)

def create_watchlist_remove_callback(address: str) -> str:
    return CallbackFormat.WATCHLIST_REMOVE.format(address=address)

def create_settings_set_callback(key: str, value: str) -> str:
    return CallbackFormat.SETTINGS_SET.format(key=key, value=value)

def create_mnemonic_callback(action: str) -> str:
    return f"mnemonic:{action}"

def create_page_callback(page: int) -> str:
    return CallbackFormat.PAGE.format(number=page)

def parse_callback_data(callback_data: str) -> tuple:
    """Parse callback data into action and parameters"""
    parts = callback_data.split(":")
    action = parts[0]
    subaction = parts[1] if len(parts) > 1 else None
    params = parts[2:] if len(parts) > 2 else []
    return action, subaction, params
