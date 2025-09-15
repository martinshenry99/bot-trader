"""Enhanced settings handler with real-time updates"""
import logging
from typing import Dict, Optional, Union, List
from decimal import Decimal

from bot.commands import CommandHandler, command
from db.models import Settings
from utils.validation import (
    validate_threshold,
    validate_percentage,
    validate_address
)

logger = logging.getLogger(__name__)

class EnhancedSettingsHandler(CommandHandler):
    """Enhanced handler for settings with live updates"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # Define setting validators
        self.validators = {
            'scan_min_score': self._validate_score,
            'scan_min_liquidity': self._validate_liquidity,
            'scan_min_holders': self._validate_holders,
            'max_slippage': self._validate_percentage,
            'min_profit': self._validate_percentage,
            'gas_limit': self._validate_gas,
            'insider_confidence': self._validate_score
        }
        
        # Define setting descriptions
        self.descriptions = {
            'scan_min_score': "Minimum risk score for token scanning (0-100)",
            'scan_min_liquidity': "Minimum liquidity in USD",
            'scan_min_holders': "Minimum number of token holders",
            'max_slippage': "Maximum allowed slippage percentage",
            'min_profit': "Minimum profit percentage for auto-sell",
            'gas_limit': "Maximum gas limit for transactions",
            'insider_confidence': "Minimum confidence score for insider detection"
        }
    
    @command(
        name='settings',
        help='Manage bot settings with live updates'
    )
    async def manage_settings(
        self,
        action: str,
        setting: Optional[str] = None,
        value: Optional[str] = None
    ) -> str:
        """Manage bot settings"""
        try:
            if action == 'list':
                return self._format_settings(
                    await self.settings.get_all()
                )
            
            elif action == 'get' and setting:
                if setting not in self.descriptions:
                    return f"Unknown setting: {setting}"
                
                value = await self.settings.get(setting)
                return (
                    f"Setting: {setting}\n"
                    f"Current Value: {value}\n"
                    f"Description: {self.descriptions[setting]}"
                )
            
            elif action == 'set' and setting and value:
                if setting not in self.validators:
                    return f"Unknown setting: {setting}"
                
                # Validate new value
                try:
                    validated = self.validators[setting](value)
                except ValueError as e:
                    return f"Invalid value: {str(e)}"
                
                # Update setting
                await self.settings.set(setting, validated)
                
                # Notify about live update
                return (
                    f"✅ Updated {setting} to {validated}\n"
                    "Changes are now live for all bot operations"
                )
            
            elif action == 'reset' and setting:
                if setting not in self.descriptions:
                    return f"Unknown setting: {setting}"
                
                await self.settings.reset(setting)
                return f"Reset {setting} to default value"
            
            elif action == 'reset' and not setting:
                await self.settings.reset_all()
                return "Reset all settings to default values"
            
            else:
                return (
                    "Invalid action. Use:\n"
                    "/settings list\n"
                    "/settings get <setting>\n"
                    "/settings set <setting> <value>\n"
                    "/settings reset [setting]"
                )
        
        except Exception as e:
            logger.error(f"Error in settings command: {str(e)}")
            raise
    
    def _validate_score(self, value: str) -> float:
        """Validate score value (0-100)"""
        try:
            score = float(value)
            if not 0 <= score <= 100:
                raise ValueError("Score must be between 0 and 100")
            return score
        except ValueError:
            raise ValueError("Invalid score value")
    
    def _validate_liquidity(self, value: str) -> Decimal:
        """Validate liquidity value (>0)"""
        try:
            liquidity = Decimal(value)
            if liquidity <= 0:
                raise ValueError("Liquidity must be positive")
            return liquidity
        except ValueError:
            raise ValueError("Invalid liquidity value")
    
    def _validate_holders(self, value: str) -> int:
        """Validate holder count (>0)"""
        try:
            holders = int(value)
            if holders <= 0:
                raise ValueError("Holder count must be positive")
            return holders
        except ValueError:
            raise ValueError("Invalid holder count")
    
    def _validate_percentage(self, value: str) -> float:
        """Validate percentage value (0-100)"""
        try:
            percentage = float(value)
            if not 0 <= percentage <= 100:
                raise ValueError("Percentage must be between 0 and 100")
            return percentage
        except ValueError:
            raise ValueError("Invalid percentage value")
    
    def _validate_gas(self, value: str) -> int:
        """Validate gas limit (>0)"""
        try:
            gas = int(value)
            if gas <= 0:
                raise ValueError("Gas limit must be positive")
            return gas
        except ValueError:
            raise ValueError("Invalid gas limit")
    
    def _format_settings(self, settings: Dict) -> str:
        """Format settings for display"""
        lines = ["📊 Current Settings"]
        
        for key, value in sorted(settings.items()):
            if key in self.descriptions:
                lines.extend([
                    "",
                    f"Setting: {key}",
                    f"Value: {value}",
                    f"Description: {self.descriptions[key]}"
                ])
        
        return "\n".join(lines)
