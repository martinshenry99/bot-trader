"""
Tests for multi-chain monitoring services
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from monitor.chain_monitor import ChainMonitor
from services.chain_manager import ChainManager
from services.helius import HeliusClient
from services.covalent import CovalentClient

# Sample test data
SAMPLE_SOL_TX = {
    'sourceAddress': 'sol_wallet_1',
    'destinationAddress': 'sol_wallet_2',
    'tokenAddress': 'sol_token_1',
    'amount': '1000000000',
    'usd_value': '15000.00',
    'timestamp': int(datetime.now().timestamp()),
    'signature': '0x123'
}

SAMPLE_BSC_TX = {
    'from_address': 'bsc_wallet_1',
    'to_address': 'bsc_wallet_2',
    'contract_address': 'bsc_token_1',
    'value': '15000000000000000000000',
    'gas_price': '5000000000',
    'gas_used': '21000',
    'block_height': 12345,
    'successful': True
}

SAMPLE_TOKEN_INFO = {
    'name': 'Test Token',
    'symbol': 'TEST',
    'decimals': 18,
    'total_supply': '1000000000000000000000000000'
}

@pytest.fixture
async def mock_chain_manager():
    manager = Mock(spec=ChainManager)
    manager.monitor_wallets = AsyncMock(return_value={
        'solana': [SAMPLE_SOL_TX],
        'bsc': [SAMPLE_BSC_TX]
    })
    manager.get_token_info = AsyncMock(return_value=SAMPLE_TOKEN_INFO)
    manager.check_transaction_confirmation = AsyncMock(return_value={
        'confirmed': True,
        'confirmations': 5
    })
    manager.analyze_wallet_activity = AsyncMock(return_value={
        'transaction_count': 100,
        'unique_tokens': 10,
        'total_value': Decimal('50000'),
        'risk_factors': {
            'mixed_funds': False,
            'contract_interactions': 5
        }
    })
    manager.find_related_wallets = AsyncMock(return_value=[
        'related_wallet_1',
        'related_wallet_2'
    ])
    return manager

@pytest.fixture
async def monitor(mock_chain_manager):
    return ChainMonitor(mock_chain_manager)

@pytest.mark.asyncio
async def test_add_wallet_monitor(monitor):
    """Test adding wallets to monitoring"""
    await monitor.add_wallet_monitor('solana', 'sol_wallet_1')
    await monitor.add_wallet_monitor('bsc', 'bsc_wallet_1')
    
    assert 'sol_wallet_1' in monitor.monitored_wallets['solana']
    assert 'bsc_wallet_1' in monitor.monitored_wallets['bsc']
    
    with pytest.raises(ValueError):
        await monitor.add_wallet_monitor('invalid_chain', 'wallet')

@pytest.mark.asyncio
async def test_add_token_monitor(monitor, mock_chain_manager):
    """Test adding tokens to monitoring"""
    await monitor.add_token_monitor('solana', 'sol_token_1')
    await monitor.add_token_monitor('bsc', 'bsc_token_1')
    
    assert 'sol_token_1' in monitor.monitored_tokens['solana']
    assert 'bsc_token_1' in monitor.monitored_tokens['bsc']
    
    # Verify token info was cached
    assert mock_chain_manager.get_token_info.call_count == 2
    assert 'solana:sol_token_1' in monitor._token_cache
    assert 'bsc:bsc_token_1' in monitor._token_cache

@pytest.mark.asyncio
async def test_process_transaction(monitor, mock_chain_manager):
    """Test transaction processing"""
    # Add monitored wallet and token
    await monitor.add_wallet_monitor('solana', 'sol_wallet_1')
    await monitor.add_token_monitor('solana', 'sol_token_1')
    
    # Process Solana transaction
    await monitor._process_transaction('solana', SAMPLE_SOL_TX)
    
    # Verify confirmations were checked
    mock_chain_manager.check_transaction_confirmation.assert_called_once()
    
    # Verify token analysis for monitored token
    assert mock_chain_manager.get_token_info.call_count > 0
    
    # Verify wallet analysis for monitored wallet
    assert mock_chain_manager.analyze_wallet_activity.call_count > 0

@pytest.mark.asyncio
async def test_high_value_detection(monitor, mock_chain_manager):
    """Test high value transfer detection"""
    # Add monitored wallet
    await monitor.add_wallet_monitor('bsc', 'bsc_wallet_1')
    
    # Modify sample transaction to trigger high value alert
    high_value_tx = SAMPLE_BSC_TX.copy()
    high_value_tx['value'] = str(int(monitor.value_threshold) * 10**18)
    
    # Process transaction
    await monitor._process_transaction('bsc', high_value_tx)
    
    # Verify wallet analysis was performed
    mock_chain_manager.analyze_wallet_activity.assert_called_with(
        'bsc',
        'bsc_wallet_1'
    )

@pytest.mark.asyncio
async def test_whale_detection(monitor, mock_chain_manager):
    """Test whale activity detection"""
    # Add monitored wallet
    await monitor.add_wallet_monitor('solana', 'sol_wallet_1')
    
    # Modify sample transaction to trigger whale alert
    whale_tx = SAMPLE_SOL_TX.copy()
    whale_tx['usd_value'] = str(float(monitor.whale_threshold))
    
    # Process transaction
    await monitor._process_transaction('solana', whale_tx)
    
    # Verify related wallets were checked
    mock_chain_manager.find_related_wallets.assert_called_with(
        'solana',
        'sol_wallet_1'
    )

@pytest.mark.asyncio
async def test_monitor_cycle(monitor, mock_chain_manager):
    """Test full monitoring cycle"""
    # Add monitored wallets and tokens
    await monitor.add_wallet_monitor('solana', 'sol_wallet_1')
    await monitor.add_wallet_monitor('bsc', 'bsc_wallet_1')
    await monitor.add_token_monitor('solana', 'sol_token_1')
    await monitor.add_token_monitor('bsc', 'bsc_token_1')
    
    # Run monitoring cycle
    await monitor._monitor_cycle()
    
    # Verify wallets were monitored
    mock_chain_manager.monitor_wallets.assert_called_with(
        solana_wallets=['sol_wallet_1'],
        bsc_wallets=['bsc_wallet_1']
    )
    
    # Verify transaction processing
    assert mock_chain_manager.check_transaction_confirmation.call_count >= 2
    assert mock_chain_manager.analyze_wallet_activity.call_count >= 2

@pytest.mark.asyncio
async def test_token_cache(monitor, mock_chain_manager):
    """Test token info caching"""
    await monitor.add_token_monitor('solana', 'sol_token_1')
    
    # First call should hit API
    token_info_1 = await monitor._get_token_info('solana', 'sol_token_1')
    assert mock_chain_manager.get_token_info.call_count == 1
    
    # Second call should use cache
    token_info_2 = await monitor._get_token_info('solana', 'sol_token_1')
    assert mock_chain_manager.get_token_info.call_count == 1
    assert token_info_1 == token_info_2
    
    # Wait for cache to expire
    monitor._last_token_update['solana:sol_token_1'] -= timedelta(
        seconds=monitor.cache_ttl + 1
    )
    
    # Third call should hit API again
    await monitor._get_token_info('solana', 'sol_token_1')
    assert mock_chain_manager.get_token_info.call_count == 2

@pytest.mark.asyncio
async def test_wallet_metrics(monitor, mock_chain_manager):
    """Test wallet metrics updates"""
    await monitor.add_wallet_monitor('bsc', 'bsc_wallet_1')
    
    # Process transaction for monitored wallet
    await monitor._update_wallet_metrics(
        'bsc',
        'bsc_wallet_1',
        SAMPLE_BSC_TX,
        'out'
    )
    
    # Verify wallet analysis
    mock_chain_manager.analyze_wallet_activity.assert_called_with(
        'bsc',
        'bsc_wallet_1',
        days=7
    )
