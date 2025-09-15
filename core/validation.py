"""
Validation framework for trade safety and input validation
"""
from typing import Dict, Any, Optional, Union, List
from decimal import Decimal
import re
from web3 import Web3
import base58  # for Solana addresses
import logging

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Custom validation error"""
    pass

class TradeValidator:
    """Validates trade parameters and ensures safety"""
    
    def __init__(
        self,
        max_slippage_bps: int = 100,  # 1%
        min_liquidity_usd: int = 10000,
        max_price_impact_bps: int = 500,  # 5%
        max_wallet_exposure_pct: int = 10
    ):
        self.max_slippage_bps = max_slippage_bps
        self.min_liquidity_usd = min_liquidity_usd
        self.max_price_impact_bps = max_price_impact_bps
        self.max_wallet_exposure_pct = max_wallet_exposure_pct
    
    async def validate_trade(
        self,
        trade_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate trade parameters"""
        try:
            # Extract parameters
            chain = trade_params.get('chain', '').upper()
            token_address = trade_params.get('token_address', '')
            amount = trade_params.get('amount', 0)
            slippage = trade_params.get('slippage_bps', self.max_slippage_bps)
            
            # Basic parameter validation
            self._validate_chain(chain)
            self._validate_address(token_address, chain)
            self._validate_amount(amount)
            self._validate_slippage(slippage)
            
            # Get token info
            token_info = await self._get_token_info(
                token_address,
                chain
            )
            
            # Validate token
            self._validate_token_safety(token_info)
            
            # Validate liquidity
            self._validate_liquidity(token_info)
            
            # Validate price impact
            price_impact = self._calculate_price_impact(
                amount,
                token_info
            )
            self._validate_price_impact(price_impact)
            
            # Validate wallet exposure
            wallet_info = trade_params.get('wallet_info', {})
            self._validate_wallet_exposure(
                amount,
                wallet_info
            )
            
            # Return validated parameters with warnings
            return {
                'validated': True,
                'warnings': self._generate_warnings(
                    token_info,
                    price_impact,
                    slippage
                ),
                'suggested_slippage': self._suggest_slippage(
                    token_info,
                    price_impact
                ),
                'token_info': token_info
            }
            
        except ValidationError as e:
            logger.warning(f"Trade validation failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected validation error: {str(e)}")
            raise ValidationError(
                f"Validation failed: {str(e)}"
            )
    
    def _validate_chain(self, chain: str):
        """Validate chain identifier"""
        valid_chains = {'ETH', 'BSC', 'SOL'}
        if chain not in valid_chains:
            raise ValidationError(
                f"Invalid chain: {chain}. "
                f"Must be one of {valid_chains}"
            )
    
    def _validate_address(
        self,
        address: str,
        chain: str
    ):
        """Validate token address format"""
        try:
            if chain in {'ETH', 'BSC'}:
                # Validate EVM address
                if not Web3.is_address(address):
                    raise ValidationError(
                        f"Invalid {chain} address format"
                    )
            elif chain == 'SOL':
                # Validate Solana address
                try:
                    base58.b58decode(address)
                except Exception:
                    raise ValidationError(
                        "Invalid Solana address format"
                    )
        except Exception as e:
            raise ValidationError(f"Address validation failed: {str(e)}")
    
    def _validate_amount(
        self,
        amount: Union[int, float, str, Decimal]
    ):
        """Validate trade amount"""
        try:
            amount = Decimal(str(amount))
            if amount <= 0:
                raise ValidationError("Amount must be positive")
        except Exception as e:
            raise ValidationError(f"Invalid amount: {str(e)}")
    
    def _validate_slippage(self, slippage_bps: int):
        """Validate slippage is within limits"""
        if not isinstance(slippage_bps, int):
            raise ValidationError("Slippage must be an integer")
            
        if slippage_bps <= 0:
            raise ValidationError("Slippage must be positive")
            
        if slippage_bps > self.max_slippage_bps:
            raise ValidationError(
                f"Slippage {slippage_bps} bps exceeds "
                f"maximum {self.max_slippage_bps} bps"
            )
    
    def _validate_token_safety(
        self,
        token_info: Dict[str, Any]
    ):
        """Validate token safety parameters"""
        if token_info.get('is_honeypot'):
            raise ValidationError("Token detected as honeypot")
            
        if token_info.get('is_blacklisted'):
            raise ValidationError("Token is blacklisted")
            
        if token_info.get('is_proxy') and not token_info.get('proxy_verified'):
            raise ValidationError("Unverified proxy contract")
            
        # Check trading restrictions
        if token_info.get('cannot_sell'):
            raise ValidationError("Token cannot be sold")
            
        if token_info.get('cannot_buy'):
            raise ValidationError("Token cannot be bought")
    
    def _validate_liquidity(
        self,
        token_info: Dict[str, Any]
    ):
        """Validate token liquidity"""
        liquidity = Decimal(str(token_info.get('liquidity_usd', 0)))
        if liquidity < self.min_liquidity_usd:
            raise ValidationError(
                f"Insufficient liquidity: ${liquidity:,.2f} < "
                f"${self.min_liquidity_usd:,.2f}"
            )
    
    def _validate_price_impact(
        self,
        price_impact_bps: int
    ):
        """Validate price impact is within limits"""
        if price_impact_bps > self.max_price_impact_bps:
            raise ValidationError(
                f"Price impact too high: {price_impact_bps} bps > "
                f"{self.max_price_impact_bps} bps"
            )
    
    def _validate_wallet_exposure(
        self,
        amount: Union[int, float, str, Decimal],
        wallet_info: Dict[str, Any]
    ):
        """Validate wallet exposure limits"""
        amount = Decimal(str(amount))
        total_value = Decimal(str(wallet_info.get('total_value', 0)))
        
        if total_value > 0:
            exposure = (amount / total_value) * 100
            if exposure > self.max_wallet_exposure_pct:
                raise ValidationError(
                    f"Trade exceeds max wallet exposure: "
                    f"{exposure:.1f}% > {self.max_wallet_exposure_pct}%"
                )
    
    def _calculate_price_impact(
        self,
        amount: Union[int, float, str, Decimal],
        token_info: Dict[str, Any]
    ) -> int:
        """Calculate price impact in basis points"""
        amount = Decimal(str(amount))
        liquidity = Decimal(str(token_info.get('liquidity_usd', 0)))
        
        if liquidity > 0:
            impact = (amount / liquidity) * 10000  # Convert to bps
            return int(impact)
        return 10000  # 100% impact if no liquidity
    
    def _suggest_slippage(
        self,
        token_info: Dict[str, Any],
        price_impact_bps: int
    ) -> int:
        """Suggest appropriate slippage based on token metrics"""
        # Start with base slippage
        suggested = 100  # 1%
        
        # Adjust for volatility
        volatility = Decimal(str(token_info.get('volatility_24h', 0)))
        if volatility > 100:
            suggested += 50  # +0.5%
        
        # Adjust for liquidity
        liquidity = Decimal(str(token_info.get('liquidity_usd', 0)))
        if liquidity < 50000:
            suggested += 50  # +0.5%
        
        # Adjust for price impact
        if price_impact_bps > 100:
            suggested += price_impact_bps // 2
        
        # Cap at max allowed
        return min(suggested, self.max_slippage_bps)
    
    def _generate_warnings(
        self,
        token_info: Dict[str, Any],
        price_impact_bps: int,
        slippage_bps: int
    ) -> List[str]:
        """Generate warning messages"""
        warnings = []
        
        # Liquidity warnings
        liquidity = Decimal(str(token_info.get('liquidity_usd', 0)))
        if liquidity < 50000:
            warnings.append(
                f"⚠️ Low liquidity: ${liquidity:,.2f}"
            )
        
        # Price impact warnings
        if price_impact_bps > 100:
            warnings.append(
                f"⚠️ High price impact: {price_impact_bps/100}%"
            )
        
        # Slippage warnings
        if slippage_bps > 100:
            warnings.append(
                f"⚠️ High slippage: {slippage_bps/100}%"
            )
        
        # Contract warnings
        if token_info.get('is_proxy'):
            warnings.append("⚠️ Proxy contract")
        
        if token_info.get('owner_change_balance'):
            warnings.append("⚠️ Owner can modify balances")
        
        if token_info.get('trading_cooldown', 0) > 0:
            warnings.append(
                f"⚠️ Trading cooldown: "
                f"{token_info['trading_cooldown']}s"
            )
        
        return warnings
    
    async def _get_token_info(
        self,
        address: str,
        chain: str
    ) -> Dict[str, Any]:
        """Get token information and security data"""
        # This would be implemented to fetch from your APIs
        pass

class InputValidator:
    """Validates user input for commands"""
    
    @staticmethod
    def validate_command(
        command: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate command parameters"""
        validators = {
            'settings': InputValidator._validate_settings,
            'buy': InputValidator._validate_buy,
            'sell': InputValidator._validate_sell,
            'add_wallet': InputValidator._validate_wallet,
            'set_alert': InputValidator._validate_alert
        }
        
        validator = validators.get(command)
        if not validator:
            raise ValidationError(f"Unknown command: {command}")
            
        return validator(params)
    
    @staticmethod
    def _validate_settings(params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate settings parameters"""
        valid_keys = {
            'max_slippage_bps',
            'scan_interval',
            'alert_threshold',
            'auto_buy',
            'safe_mode'
        }
        
        invalid_keys = set(params.keys()) - valid_keys
        if invalid_keys:
            raise ValidationError(
                f"Invalid settings: {invalid_keys}"
            )
        
        # Validate specific settings
        if 'max_slippage_bps' in params:
            value = params['max_slippage_bps']
            if not isinstance(value, int) or value <= 0 or value > 1000:
                raise ValidationError(
                    "max_slippage_bps must be 1-1000"
                )
        
        if 'scan_interval' in params:
            value = params['scan_interval']
            if not isinstance(value, int) or value < 10 or value > 3600:
                raise ValidationError(
                    "scan_interval must be 10-3600 seconds"
                )
        
        if 'alert_threshold' in params:
            value = params['alert_threshold']
            if not isinstance(value, (int, float)) or value <= 0:
                raise ValidationError(
                    "alert_threshold must be positive"
                )
        
        if 'auto_buy' in params:
            if not isinstance(params['auto_buy'], bool):
                raise ValidationError(
                    "auto_buy must be true/false"
                )
        
        if 'safe_mode' in params:
            if not isinstance(params['safe_mode'], bool):
                raise ValidationError(
                    "safe_mode must be true/false"
                )
        
        return params
    
    @staticmethod
    def _validate_buy(params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate buy parameters"""
        required = {'token', 'amount'}
        missing = required - set(params.keys())
        if missing:
            raise ValidationError(
                f"Missing required parameters: {missing}"
            )
        
        # Validate token address
        if not re.match(r'^0x[a-fA-F0-9]{40}$', params['token']):
            raise ValidationError(
                "Invalid token address format"
            )
        
        # Validate amount
        try:
            amount = Decimal(str(params['amount']))
            if amount <= 0:
                raise ValidationError(
                    "Amount must be positive"
                )
        except:
            raise ValidationError(
                "Invalid amount format"
            )
        
        return params
    
    @staticmethod
    def _validate_sell(params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate sell parameters"""
        required = {'token', 'percentage'}
        missing = required - set(params.keys())
        if missing:
            raise ValidationError(
                f"Missing required parameters: {missing}"
            )
        
        # Validate token address
        if not re.match(r'^0x[a-fA-F0-9]{40}$', params['token']):
            raise ValidationError(
                "Invalid token address format"
            )
        
        # Validate percentage
        try:
            pct = Decimal(str(params['percentage']))
            if pct <= 0 or pct > 100:
                raise ValidationError(
                    "Percentage must be 1-100"
                )
        except:
            raise ValidationError(
                "Invalid percentage format"
            )
        
        return params
    
    @staticmethod
    def _validate_wallet(params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate wallet parameters"""
        required = {'address', 'chain'}
        missing = required - set(params.keys())
        if missing:
            raise ValidationError(
                f"Missing required parameters: {missing}"
            )
        
        # Validate chain
        if params['chain'] not in {'ETH', 'BSC', 'SOL'}:
            raise ValidationError(
                "Invalid chain"
            )
        
        # Validate address format
        if params['chain'] in {'ETH', 'BSC'}:
            if not re.match(r'^0x[a-fA-F0-9]{40}$', params['address']):
                raise ValidationError(
                    "Invalid EVM address format"
                )
        else:  # Solana
            try:
                base58.b58decode(params['address'])
            except:
                raise ValidationError(
                    "Invalid Solana address format"
                )
        
        return params
    
    @staticmethod
    def _validate_alert(params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate alert parameters"""
        required = {'type', 'value'}
        missing = required - set(params.keys())
        if missing:
            raise ValidationError(
                f"Missing required parameters: {missing}"
            )
        
        # Validate alert type
        valid_types = {
            'price',
            'volume',
            'liquidity',
            'wallet'
        }
        if params['type'] not in valid_types:
            raise ValidationError(
                f"Invalid alert type. Must be one of: {valid_types}"
            )
        
        # Validate value based on type
        try:
            if params['type'] in {'price', 'volume', 'liquidity'}:
                value = Decimal(str(params['value']))
                if value <= 0:
                    raise ValidationError(
                        "Value must be positive"
                    )
            elif params['type'] == 'wallet':
                if not isinstance(params['value'], str):
                    raise ValidationError(
                        "Wallet address must be string"
                    )
        except:
            raise ValidationError(
                "Invalid value format"
            )
        
        return params
