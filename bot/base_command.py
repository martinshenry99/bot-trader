"""
Base command handler with shared functionality
"""

import logging
from typing import Optional, Dict, Any, Tuple
from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from utils.validation import (
    validate_chain,
    validate_address,
    validate_amount,
    validate_percentage,
    validate_slippage,
    validate_api_key,
    validate_gas_price,
    validate_settings,
    ValidationError
)

logger = logging.getLogger(__name__)

class BaseCommand:
    """Base class for command handlers with shared functionality"""
    
    def __init__(self):
        self.safe_mode = Config.SAFE_MODE
        self.admin_id = Config.ADMIN_TELEGRAM_ID
        
    async def check_admin(self, update: Update) -> bool:
        """Check if user is admin"""
        user_id = update.effective_user.id
        is_admin = str(user_id) == str(self.admin_id)
        if not is_admin:
            await update.message.reply_text("⚠️ This command is for administrators only.")
        return is_admin

    async def ensure_user_exists(self, update: Update) -> bool:
        """Ensure user exists in database"""
        from db.models import get_db_manager
        
        user_id = str(update.effective_user.id)
        db = get_db_manager()
        
        try:
            user = await db.get_user(user_id)
            if not user:
                await db.create_user(
                    telegram_id=user_id,
                    username=update.effective_user.username,
                    first_name=update.effective_user.first_name,
                    last_name=update.effective_user.last_name
                )
                logger.info(f"Created new user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error ensuring user exists: {e}")
            await update.message.reply_text(
                "❌ Error accessing user database. Please try again later."
            )
            return False

    async def get_user_settings(self, user_id: str) -> Dict[str, Any]:
        """Get user settings with defaults"""
        from db.models import get_db_manager
        
        db = get_db_manager()
        settings = await db.get_user_settings(user_id)
        
        # Apply defaults if not set
        defaults = {
            "scan_min_roi": 1.5,
            "scan_min_trades": 10,
            "scan_min_score": 50,
            "alert_min_usd": 1000,
            "buy_size_min_usd": 50,
            "max_slippage": 0.05,
            "stop_loss_percentage": 0.2,
            "take_profit_multiplier": 2.0,
            "alert_frequency": 300  # 5 minutes
        }
        
        for key, default_value in defaults.items():
            if key not in settings:
                settings[key] = default_value
                
        return settings

    def validate_chain(self, chain: str) -> bool:
        """Validate chain is supported"""
        return validate_chain(chain)

    def validate_address(self, address: str, chain: str) -> bool:
        """Validate address format for chain"""
        return validate_address(address, chain)
        
    def validate_trade_inputs(
        self,
        chain: str,
        token_address: str,
        amount: Union[int, float, str],
        slippage: Optional[Union[int, float, str]] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validate trade inputs"""
        try:
            if not validate_chain(chain):
                return False, f"Unsupported chain: {chain}"
                
            if not validate_address(token_address, chain):
                return False, f"Invalid token address format for {chain}"
                
            if not validate_amount(amount, min_val=0):
                return False, "Invalid amount"
                
            if slippage is not None and not validate_slippage(slippage):
                return False, "Slippage must be between 0 and 100"
                
            return True, None
            
        except Exception as e:
            logger.error(f"Error validating trade inputs: {e}")
            return False, "Invalid input parameters"
            
    def validate_scan_inputs(
        self,
        min_score: Optional[Union[int, float, str]] = None,
        min_trades: Optional[Union[int, float, str]] = None,
        min_volume: Optional[Union[int, float, str]] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validate scan parameters"""
        try:
            if min_score is not None and not validate_percentage(min_score):
                return False, "Min score must be between 0 and 100"
                
            if min_trades is not None and not validate_amount(min_trades, min_val=1):
                return False, "Min trades must be at least 1"
                
            if min_volume is not None and not validate_amount(min_volume, min_val=0):
                return False, "Min volume must be at least 0"
                
            return True, None
            
        except Exception as e:
            logger.error(f"Error validating scan inputs: {e}")
            return False, "Invalid scan parameters"
