"""
Test suite for trading engine and execution
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch
from core.trading_engine import trading_engine
from services.key_manager import get_key_manager
from config import Config

# Sample test data
SAMPLE_TOKEN = {
    'address': '0xtoken...',
    'chain': 'ethereum',
    'name': 'Test Token',
    'symbol': 'TEST',
    'decimals': 18
}

SAMPLE_QUOTE = {
    'price': '1.0',
    'gas_price': '50000000000',
    'gas': '200000',
    'protocol': '0x',
    'route': []
}

@pytest.fixture
async def engine():
    """Create test trading engine instance"""
    engine = trading_engine
    await engine.initialize()
    yield engine
    await engine.shutdown()

@pytest.mark.asyncio
async def test_buy_preflight_checks(engine):
    """Test buy preflight safety checks"""
    # Mock dependencies
    engine.goplus_client.check_token = Mock(return_value={
        'is_honeypot': False,
        'buy_tax': '5',
        'sell_tax': '5',
        'total_supply': '1000000000000000000000000',
        'holders': 1000,
        'is_mintable': False
    })
    
    engine.get_token_quote = Mock(return_value=SAMPLE_QUOTE)
    
    # Run preflight checks
    result = await engine.run_buy_preflight(
        token_address='0xtoken...',
        chain='ethereum',
        amount_usd=100.0
    )
    
    assert result['can_proceed'] == True
    assert result['quote'] is not None
    assert result['safety_checks']['is_honeypot'] == False

@pytest.mark.asyncio
async def test_safe_mode_blocking(engine):
    """Test safe mode blocks risky trades"""
    # Enable safe mode
    engine.config['safe_mode'] = True
    
    # Mock risky token
    engine.goplus_client.check_token = Mock(return_value={
        'is_honeypot': True,
        'buy_tax': '99',
        'sell_tax': '99',
        'total_supply': '1000000000000000000000000',
        'holders': 10,
        'is_mintable': True
    })
    
    # Run preflight checks
    result = await engine.run_buy_preflight(
        token_address='0xtoken...',
        chain='ethereum',
        amount_usd=100.0
    )
    
    assert result['can_proceed'] == False
    assert 'honeypot' in result['block_reasons']

@pytest.mark.asyncio
async def test_key_rotation_on_rate_limit(engine):
    """Test API key rotation on rate limit"""
    from services.api_manager import RateLimitError
    
    # Mock rate limited response
    engine.zerox_client.get_quote = Mock(
        side_effect=RateLimitError(retry_after=60)
    )
    
    # Get initial key
    initial_key = await get_key_manager().get_key('zerox')
    
    try:
        # Attempt quote
        await engine.get_token_quote(
            token_address='0xtoken...',
            chain='ethereum',
            amount_usd=100.0
        )
    except RateLimitError:
        pass
        
    # Get new key
    new_key = await get_key_manager().get_key('zerox')
    
    assert initial_key != new_key

@pytest.mark.asyncio
async def test_buy_workflow(engine):
    """Test complete buy workflow"""
    # Mock dependencies
    engine.goplus_client.check_token = Mock(return_value={
        'is_honeypot': False,
        'buy_tax': '5',
        'sell_tax': '5'
    })
    
    engine.get_token_quote = Mock(return_value=SAMPLE_QUOTE)
    
    engine.zerox_client.execute_swap = Mock(return_value={
        'tx_hash': '0x123...',
        'status': 'success'
    })
    
    # Run buy workflow
    result = await engine.execute_buy(
        token_address='0xtoken...',
        chain='ethereum',
        amount_usd=100.0
    )
    
    assert result['success'] == True
    assert result['tx_hash'] == '0x123...'

@pytest.mark.asyncio
async def test_sell_workflow(engine):
    """Test complete sell workflow"""
    # Mock dependencies
    engine.get_token_balance = Mock(return_value='1000000000000000000')
    
    engine.get_token_quote = Mock(return_value=SAMPLE_QUOTE)
    
    engine.zerox_client.execute_swap = Mock(return_value={
        'tx_hash': '0x123...',
        'status': 'success'
    })
    
    # Run sell workflow
    result = await engine.execute_sell(
        token_address='0xtoken...',
        chain='ethereum',
        percent=100
    )
    
    assert result['success'] == True
    assert result['tx_hash'] == '0x123...'

@pytest.mark.asyncio
async def test_error_handling(engine):
    """Test error handling and retries"""
    from aiohttp import ClientError
    
    # Mock failing request with retry
    call_count = 0
    async def mock_quote(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ClientError()
        return SAMPLE_QUOTE
    
    engine.zerox_client.get_quote = Mock(side_effect=mock_quote)
    
    # Should succeed after retries
    quote = await engine.get_token_quote(
        token_address='0xtoken...',
        chain='ethereum',
        amount_usd=100.0
    )
    
    assert quote == SAMPLE_QUOTE
    assert call_count == 3
