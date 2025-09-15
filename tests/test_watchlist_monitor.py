"""
Core test suite for watchlist monitoring and alert system
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from monitor.watchlist_monitor import WatchlistMonitor, TradeAlert
from services.key_manager import get_key_manager
from config import Config

# Sample test data
SAMPLE_ETH_TX = {
    'hash': '0x123...',
    'from': '0xabc...',
    'to': '0xdef...',
    'value': '1000000000000000000',
    'log_events': [
        {
            'decoded': {
                'name': 'Transfer',
                'params': [
                    {'value': '0xabc...'},
                    {'value': '0xdef...'},
                    {'value': '1000000000'}
                ]
            }
        }
    ]
}

SAMPLE_SOL_TX = {
    'signature': '4Rk7...',
    'blockTime': int(datetime.now().timestamp()),
    'instructions': [
        {
            'programId': 'JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB',
            'accounts': ['addr1', 'addr2']
        }
    ]
}

@pytest.fixture
async def monitor():
    """Create test monitor instance"""
    monitor = WatchlistMonitor()
    await monitor.initialize()
    yield monitor
    await monitor.stop_monitoring()

@pytest.mark.asyncio
async def test_monitor_initialization(monitor):
    """Test monitor initializes correctly"""
    assert monitor.monitoring == False
    assert monitor.db is not None
    assert monitor.key_manager is not None
    assert isinstance(monitor.alert_cache, set)
    assert isinstance(monitor.consensus_cache, dict)

@pytest.mark.asyncio
async def test_evm_trade_detection(monitor):
    """Test EVM chain trade detection"""
    # Mock dependencies
    monitor.db.get_user_watchlist = Mock(return_value=[
        {'address': '0xabc...', 'chain': 'ethereum'}
    ])
    monitor.covalent_client.get_recent_transactions = Mock(
        return_value=[SAMPLE_ETH_TX]
    )
    
    # Process transaction
    alert = await monitor._create_trade_alert(
        {'address': '0xabc...', 'chain': 'ethereum'},
        SAMPLE_ETH_TX,
        'ethereum'
    )
    
    assert alert is not None
    assert alert.wallet_address == '0xabc...'
    assert alert.chain == 'ethereum'
    assert alert.action in ['BUY', 'SELL']

@pytest.mark.asyncio
async def test_solana_trade_detection(monitor):
    """Test Solana trade detection"""
    # Mock dependencies
    monitor.db.get_user_watchlist = Mock(return_value=[
        {'address': 'addr1', 'chain': 'solana'}
    ])
    monitor.helius_client.get_recent_transactions = Mock(
        return_value=[SAMPLE_SOL_TX]
    )
    
    # Process transaction
    alert = await monitor._create_solana_alert(
        {'address': 'addr1', 'chain': 'solana'},
        SAMPLE_SOL_TX
    )
    
    assert alert is not None
    assert alert.wallet_address == 'addr1'
    assert alert.chain == 'solana'

@pytest.mark.asyncio
async def test_alert_deduplication(monitor):
    """Test alert deduplication logic"""
    alert1 = TradeAlert(
        wallet_address='0xabc...',
        wallet_label='Trader 1',
        chain='ethereum',
        action='BUY',
        token_address='0xtoken...',
        token_name='Test Token',
        token_symbol='TEST',
        amount_tokens=1000.0,
        amount_usd=1000.0,
        tx_hash='0x123...',
        timestamp=datetime.now(),
        trader_win_rate=80.0,
        trader_roi=2.5,
        trader_trades_30d=50,
        risk_score=20,
        is_safe=True
    )
    
    # First alert should be sent
    assert monitor._should_send_alert(alert1) == True
    
    # Duplicate alert should be blocked
    assert monitor._should_send_alert(alert1) == False

@pytest.mark.asyncio
async def test_consensus_detection(monitor):
    """Test consensus buy detection"""
    now = datetime.now()
    alerts = [
        TradeAlert(
            wallet_address=f'0xabc{i}...',
            wallet_label=f'Trader {i}',
            chain='ethereum',
            action='BUY',
            token_address='0xtoken...',
            token_name='Test Token',
            token_symbol='TEST',
            amount_tokens=1000.0,
            amount_usd=1000.0,
            tx_hash=f'0x123{i}...',
            timestamp=now - timedelta(minutes=i),
            trader_win_rate=80.0,
            trader_roi=2.5,
            trader_trades_30d=50,
            risk_score=20,
            is_safe=True
        )
        for i in range(3)
    ]
    
    # Mock database
    monitor.db.get_recent_alerts = Mock(return_value=alerts)
    
    # Check consensus detection
    await monitor._check_consensus_patterns()
    
    # Verify consensus alert was created
    consensus_calls = monitor.db.store_consensus_alert.call_count
    assert consensus_calls == 1

@pytest.mark.asyncio
async def test_webhook_signature_verification():
    """Test webhook signature verification"""
    from monitor.webhook_handler import verify_helius_signature
    
    # Test data
    test_secret = "test_secret_123"
    test_data = {"event": "transaction"}
    
    with patch.dict(Config.__dict__, {'HELIUS_WEBHOOK_SECRET': test_secret}):
        # Generate signature
        import hmac
        import hashlib
        message = str(test_data).encode('utf-8')
        signature = hmac.new(
            test_secret.encode('utf-8'),
            message,
            hashlib.sha256
        ).hexdigest()
        
        # Verify signature
        assert verify_helius_signature(signature, test_data) == True
        assert verify_helius_signature("invalid_sig", test_data) == False

@pytest.mark.asyncio
async def test_alert_persistence(monitor):
    """Test alert database persistence"""
    alert = TradeAlert(
        wallet_address='0xabc...',
        wallet_label='Trader 1',
        chain='ethereum',
        action='BUY',
        token_address='0xtoken...',
        token_name='Test Token',
        token_symbol='TEST',
        amount_tokens=1000.0,
        amount_usd=1000.0,
        tx_hash='0x123...',
        timestamp=datetime.now(),
        trader_win_rate=80.0,
        trader_roi=2.5,
        trader_trades_30d=50,
        risk_score=20,
        is_safe=True
    )
    
    # Store alert
    await monitor._send_trade_alert(alert)
    
    # Verify alert was stored
    stored_alert = monitor.db.get_alert(alert.tx_hash)
    assert stored_alert is not None
    assert stored_alert.tx_hash == alert.tx_hash
