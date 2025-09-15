"""
Test suite for validation framework
"""
import pytest
from decimal import Decimal
from core.validation import TradeValidator, InputValidator, ValidationError

@pytest.fixture
def trade_validator():
    return TradeValidator(
        max_slippage_bps=100,  # 1%
        min_liquidity_usd=10000,
        max_price_impact_bps=500,  # 5%
        max_wallet_exposure_pct=10
    )

@pytest.fixture
def sample_trade_params():
    return {
        'chain': 'ETH',
        'token_address': '0x1234567890123456789012345678901234567890',
        'amount': '1000',
        'slippage_bps': 50,
        'wallet_info': {
            'total_value': '10000'
        }
    }

@pytest.fixture
def sample_token_info():
    return {
        'is_honeypot': False,
        'is_blacklisted': False,
        'is_proxy': False,
        'proxy_verified': True,
        'cannot_sell': False,
        'cannot_buy': False,
        'liquidity_usd': '50000',
        'volatility_24h': '50',
        'owner_change_balance': False,
        'trading_cooldown': 0
    }

class TestTradeValidator:
    async def test_validate_trade_success(
        self,
        trade_validator,
        sample_trade_params,
        sample_token_info,
        mocker
    ):
        # Mock token info fetch
        mocker.patch.object(
            trade_validator,
            '_get_token_info',
            return_value=sample_token_info
        )
        
        result = await trade_validator.validate_trade(
            sample_trade_params
        )
        
        assert result['validated'] is True
        assert isinstance(result['warnings'], list)
        assert isinstance(result['suggested_slippage'], int)
        assert result['token_info'] == sample_token_info

    async def test_validate_trade_honeypot(
        self,
        trade_validator,
        sample_trade_params,
        sample_token_info,
        mocker
    ):
        sample_token_info['is_honeypot'] = True
        mocker.patch.object(
            trade_validator,
            '_get_token_info',
            return_value=sample_token_info
        )
        
        with pytest.raises(ValidationError, match="honeypot"):
            await trade_validator.validate_trade(
                sample_trade_params
            )

    async def test_validate_trade_low_liquidity(
        self,
        trade_validator,
        sample_trade_params,
        sample_token_info,
        mocker
    ):
        sample_token_info['liquidity_usd'] = '5000'
        mocker.patch.object(
            trade_validator,
            '_get_token_info',
            return_value=sample_token_info
        )
        
        with pytest.raises(ValidationError, match="liquidity"):
            await trade_validator.validate_trade(
                sample_trade_params
            )

    def test_validate_chain(self, trade_validator):
        trade_validator._validate_chain('ETH')
        trade_validator._validate_chain('BSC')
        trade_validator._validate_chain('SOL')
        
        with pytest.raises(ValidationError):
            trade_validator._validate_chain('INVALID')

    def test_validate_address(self, trade_validator):
        # Valid ETH/BSC address
        trade_validator._validate_address(
            '0x1234567890123456789012345678901234567890',
            'ETH'
        )
        
        # Valid Solana address (example)
        trade_validator._validate_address(
            '5U3bH5b6XtG8sqFHYBDRzgZrtEJ2rdWxaYwmxscHQyuh',
            'SOL'
        )
        
        # Invalid addresses
        with pytest.raises(ValidationError):
            trade_validator._validate_address(
                'invalid',
                'ETH'
            )
        
        with pytest.raises(ValidationError):
            trade_validator._validate_address(
                'invalid',
                'SOL'
            )

    def test_validate_amount(self, trade_validator):
        trade_validator._validate_amount('100')
        trade_validator._validate_amount(100)
        trade_validator._validate_amount(Decimal('100.5'))
        
        with pytest.raises(ValidationError):
            trade_validator._validate_amount('invalid')
        
        with pytest.raises(ValidationError):
            trade_validator._validate_amount('-100')
        
        with pytest.raises(ValidationError):
            trade_validator._validate_amount('0')

class TestInputValidator:
    def test_validate_settings(self):
        # Test valid settings
        valid_settings = {
            'max_slippage_bps': 100,
            'scan_interval': 30,
            'alert_threshold': 1.5,
            'auto_buy': True,
            'safe_mode': False
        }
        
        result = InputValidator._validate_settings(valid_settings)
        assert result == valid_settings
        
        # Test invalid settings
        invalid_settings = {
            'max_slippage_bps': -1,
            'scan_interval': 5,
            'alert_threshold': 0,
            'auto_buy': 'invalid',
            'safe_mode': 1
        }
        
        with pytest.raises(ValidationError):
            InputValidator._validate_settings(
                {'max_slippage_bps': -1}
            )
        
        with pytest.raises(ValidationError):
            InputValidator._validate_settings(
                {'scan_interval': 5}
            )
        
        with pytest.raises(ValidationError):
            InputValidator._validate_settings(
                {'alert_threshold': 0}
            )
        
        with pytest.raises(ValidationError):
            InputValidator._validate_settings(
                {'auto_buy': 'invalid'}
            )
        
        with pytest.raises(ValidationError):
            InputValidator._validate_settings(
                {'safe_mode': 1}
            )

    def test_validate_buy(self):
        # Test valid buy params
        valid_params = {
            'token': '0x1234567890123456789012345678901234567890',
            'amount': '100'
        }
        
        result = InputValidator._validate_buy(valid_params)
        assert result == valid_params
        
        # Test missing params
        with pytest.raises(ValidationError):
            InputValidator._validate_buy({'token': '0x123'})
        
        with pytest.raises(ValidationError):
            InputValidator._validate_buy({'amount': '100'})
        
        # Test invalid token
        with pytest.raises(ValidationError):
            InputValidator._validate_buy({
                'token': 'invalid',
                'amount': '100'
            })
        
        # Test invalid amount
        with pytest.raises(ValidationError):
            InputValidator._validate_buy({
                'token': '0x1234567890123456789012345678901234567890',
                'amount': 'invalid'
            })
        
        with pytest.raises(ValidationError):
            InputValidator._validate_buy({
                'token': '0x1234567890123456789012345678901234567890',
                'amount': '-100'
            })

    def test_validate_sell(self):
        # Test valid sell params
        valid_params = {
            'token': '0x1234567890123456789012345678901234567890',
            'percentage': '50'
        }
        
        result = InputValidator._validate_sell(valid_params)
        assert result == valid_params
        
        # Test missing params
        with pytest.raises(ValidationError):
            InputValidator._validate_sell({'token': '0x123'})
        
        with pytest.raises(ValidationError):
            InputValidator._validate_sell({'percentage': '50'})
        
        # Test invalid token
        with pytest.raises(ValidationError):
            InputValidator._validate_sell({
                'token': 'invalid',
                'percentage': '50'
            })
        
        # Test invalid percentage
        with pytest.raises(ValidationError):
            InputValidator._validate_sell({
                'token': '0x1234567890123456789012345678901234567890',
                'percentage': 'invalid'
            })
        
        with pytest.raises(ValidationError):
            InputValidator._validate_sell({
                'token': '0x1234567890123456789012345678901234567890',
                'percentage': '0'
            })
        
        with pytest.raises(ValidationError):
            InputValidator._validate_sell({
                'token': '0x1234567890123456789012345678901234567890',
                'percentage': '101'
            })

    def test_validate_wallet(self):
        # Test valid wallet params
        valid_eth_params = {
            'address': '0x1234567890123456789012345678901234567890',
            'chain': 'ETH'
        }
        
        valid_sol_params = {
            'address': '5U3bH5b6XtG8sqFHYBDRzgZrtEJ2rdWxaYwmxscHQyuh',
            'chain': 'SOL'
        }
        
        result = InputValidator._validate_wallet(valid_eth_params)
        assert result == valid_eth_params
        
        result = InputValidator._validate_wallet(valid_sol_params)
        assert result == valid_sol_params
        
        # Test missing params
        with pytest.raises(ValidationError):
            InputValidator._validate_wallet({'address': '0x123'})
        
        with pytest.raises(ValidationError):
            InputValidator._validate_wallet({'chain': 'ETH'})
        
        # Test invalid chain
        with pytest.raises(ValidationError):
            InputValidator._validate_wallet({
                'address': '0x1234567890123456789012345678901234567890',
                'chain': 'INVALID'
            })
        
        # Test invalid addresses
        with pytest.raises(ValidationError):
            InputValidator._validate_wallet({
                'address': 'invalid',
                'chain': 'ETH'
            })
        
        with pytest.raises(ValidationError):
            InputValidator._validate_wallet({
                'address': 'invalid',
                'chain': 'SOL'
            })

    def test_validate_alert(self):
        # Test valid alert params
        valid_price_alert = {
            'type': 'price',
            'value': '100'
        }
        
        valid_wallet_alert = {
            'type': 'wallet',
            'value': '0x1234567890123456789012345678901234567890'
        }
        
        result = InputValidator._validate_alert(valid_price_alert)
        assert result == valid_price_alert
        
        result = InputValidator._validate_alert(valid_wallet_alert)
        assert result == valid_wallet_alert
        
        # Test missing params
        with pytest.raises(ValidationError):
            InputValidator._validate_alert({'type': 'price'})
        
        with pytest.raises(ValidationError):
            InputValidator._validate_alert({'value': '100'})
        
        # Test invalid type
        with pytest.raises(ValidationError):
            InputValidator._validate_alert({
                'type': 'invalid',
                'value': '100'
            })
        
        # Test invalid values
        with pytest.raises(ValidationError):
            InputValidator._validate_alert({
                'type': 'price',
                'value': 'invalid'
            })
        
        with pytest.raises(ValidationError):
            InputValidator._validate_alert({
                'type': 'price',
                'value': '-100'
            })
        
        with pytest.raises(ValidationError):
            InputValidator._validate_alert({
                'type': 'wallet',
                'value': 123
            })
