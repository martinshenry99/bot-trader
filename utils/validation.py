"""
Input validation utilities
"""

import re
import logging
from decimal import Decimal
from typing import Dict, Any, Union, Optional, Tuple
from datetime import datetime

from services.risk_scorer import RiskScorer
from integrations.goplus import GoPlusAPI
from db.models import Settings

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Validation error with details"""
    def __init__(self, message: str, field: Optional[str] = None):
        self.message = message
        self.field = field
        super().__init__(message)

def validate_chain(chain: str) -> bool:
    """Validate chain identifier"""
    valid_chains = ['eth', 'bsc', 'sol']
    return chain.lower() in valid_chains

def validate_address(address: str, chain: str) -> bool:
    """Validate address format for chain"""
    chain = chain.lower()
    
    if chain in ['eth', 'bsc']:
        # ETH/BSC address validation
        if not address.startswith('0x'):
            return False
        try:
            # Check if it's a valid hex string of correct length
            int(address[2:], 16)
            return len(address) == 42
        except ValueError:
            return False
            
    elif chain == 'sol':
        # Solana address validation
        try:
            # Base58 check
            return bool(re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', address))
        except:
            return False
            
    return False

def validate_amount(amount: Union[int, float, str], min_val: float = 0) -> bool:
    """Validate numeric amount"""
    try:
        amount = float(amount)
        return amount > min_val
    except (ValueError, TypeError):
        return False
        
def validate_percentage(value: Union[int, float, str]) -> bool:
    """Validate percentage value (0-100)"""
    try:
        value = float(value)
        return 0 <= value <= 100
    except (ValueError, TypeError):
        return False
        
def validate_slippage(value: Union[int, float, str]) -> bool:
    """Validate slippage value (0-100)"""
    return validate_percentage(value)
    
def validate_api_key(key: str, service: str) -> bool:
    """Validate API key format for service"""
    if not key:
        return False
        
    # Service-specific validation
    if service == "covalent":
        return len(key) == 64 and key.isalnum()
    elif service in ["alchemy", "infura"]:
        return key.startswith("0x") and len(key) >= 32
    elif service == "helius":
        return len(key) >= 32 and key.isalnum()
    elif service == "bscscan":
        return len(key) >= 32 and key.isalnum()
    elif service == "etherscan":
        return len(key) >= 32 and key.isalnum()
    elif service == "solscan":
        return len(key) >= 32 and key.isalnum()
        
    return True  # Default to true for unknown services
    
def validate_gas_price(value: Union[int, float, str], chain: str) -> bool:
    """Validate gas price for chain"""
    try:
        value = float(value)
        if value <= 0:
            return False
            
        # Chain-specific validation
        chain = chain.lower()
        if chain == 'eth':
            return value >= 1  # Min 1 gwei
        elif chain == 'bsc':
            return value >= 3  # Min 3 gwei
        elif chain == 'sol':
            return value >= 0.000005  # Min 5000 lamports
            
        return True
        
    except (ValueError, TypeError):
        return False
        
def validate_settings(settings: Dict[str, Any]) -> Dict[str, str]:
    """Validate user settings"""
    errors = {}
    
    # Scan settings
    if 'scan_min_score' in settings:
        if not validate_percentage(settings['scan_min_score']):
            errors['scan_min_score'] = "Must be between 0 and 100"
            
    if 'scan_min_trades' in settings:
        if not validate_amount(settings['scan_min_trades'], min_val=1):
            errors['scan_min_trades'] = "Must be at least 1"
            
    # Trade settings
    if 'buy_size_min_usd' in settings:
        if not validate_amount(settings['buy_size_min_usd'], min_val=1):
            errors['buy_size_min_usd'] = "Must be at least 1 USD"
            
    if 'max_slippage' in settings:
        if not validate_slippage(settings['max_slippage']):
            errors['max_slippage'] = "Must be between 0 and 100"
            
    if 'stop_loss_percentage' in settings:
        if not validate_percentage(settings['stop_loss_percentage']):
            errors['stop_loss_percentage'] = "Must be between 0 and 100"
            
    if 'take_profit_multiplier' in settings:
        if not validate_amount(settings['take_profit_multiplier'], min_val=1):
            errors['take_profit_multiplier'] = "Must be at least 1x"
            
    # Alert settings
    if 'alert_min_usd' in settings:
        if not validate_amount(settings['alert_min_usd'], min_val=0):
            errors['alert_min_usd'] = "Must be at least 0 USD"
            
    if 'alert_frequency' in settings:
        if not validate_amount(settings['alert_frequency'], min_val=60):
            errors['alert_frequency'] = "Must be at least 60 seconds"
            
    return errors
