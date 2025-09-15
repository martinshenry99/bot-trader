"""Tests for token discovery and monitoring system"""
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from services.token_discovery import TokenDiscovery
from handlers.discovery_handler import TokenDiscoveryHandler

@pytest.fixture
def mock_market_research():
    mock = AsyncMock()
    mock.get_token_analysis = AsyncMock()
    return mock

@pytest.fixture
def mock_risk_scorer():
    mock = AsyncMock()
    mock.calculate_risk_score = AsyncMock()
    return mock

@pytest.fixture
def mock_covalent():
    mock = AsyncMock()
    mock.get_new_pairs = AsyncMock()
    return mock

@pytest.fixture
def mock_goplus():
    mock = AsyncMock()
    return mock

@pytest.fixture
def discovery_service(
    mock_market_research,
    mock_risk_scorer,
    mock_covalent,
    mock_goplus
):
    return TokenDiscovery(
        mock_market_research,
        mock_risk_scorer,
        mock_covalent,
        mock_goplus
    )

@pytest.mark.asyncio
async def test_discover_tokens(discovery_service, mock_covalent):
    # Setup test data
    token_address = "0x123..."
    mock_covalent.get_new_pairs.return_value = [{
        'token_address': token_address
    }]
    
    # Mock analysis data
    discovery_service._analyze_token = AsyncMock()
    discovery_service._analyze_token.return_value = {
        'symbol': 'TEST',
        'name': 'Test Token',
        'liquidity': Decimal('20000'),
        'volume_24h': Decimal('10000'),
        'holder_count': 100,
        'holder_concentration': 0.5,
        'price_usd': Decimal('1.0'),
        'market_cap': Decimal('1000000'),
        'risk_score': 0.5,
        'risk_factors': {'code_risk': 0.3},
        'security_info': {'is_honeypot': False}
    }
    
    # Test discovery
    discovered = await discovery_service.discover_tokens('ethereum')
    
    assert len(discovered) == 1
    assert discovered[0]['token_address'] == token_address
    assert discovered[0]['symbol'] == 'TEST'
    assert float(discovered[0]['liquidity']) == 20000
    assert float(discovered[0]['risk_score']) == 0.5

@pytest.mark.asyncio
async def test_monitor_tokens(discovery_service):
    # Setup test data
    token_address = "0x123..."
    discovery_service._monitored_tokens.add(token_address)
    
    # Mock analysis data
    discovery_service._analyze_token = AsyncMock()
    discovery_service._analyze_token.return_value = {
        'price_usd': Decimal('2.0'),  # Significant price change
        'volume_24h': Decimal('50000'),
        'liquidity': Decimal('20000'),
        'holder_concentration': 0.5
    }
    
    # Mock historical data for change detection
    discovery_service.market_research.get_token_analysis = AsyncMock()
    discovery_service.market_research.get_token_analysis.return_value = {
        'market_data': {
            'price_usd': Decimal('1.0'),
            'volume_24h': Decimal('10000')
        },
        'liquidity_data': {
            'total_liquidity': Decimal('20000')
        },
        'holder_analysis': {
            'top_10_holdings': 0.5
        }
    }
    
    # Test monitoring
    alerts = await discovery_service.monitor_tokens('ethereum')
    
    assert len(alerts) == 1
    assert alerts[0]['token_address'] == token_address
    assert len(alerts[0]['changes']) > 0
    assert any('Price changed' in change for change in alerts[0]['changes'])

@pytest.mark.asyncio
async def test_add_to_watchlist(discovery_service):
    token_address = "0x123..."
    
    # Mock analysis
    discovery_service._analyze_token = AsyncMock()
    discovery_service._analyze_token.return_value = {
        'symbol': 'TEST',
        'name': 'Test Token',
        'liquidity': Decimal('20000'),
        'volume_24h': Decimal('10000'),
        'holder_count': 100,
        'risk_score': 0.5
    }
    
    # Test adding to watchlist
    result = await discovery_service.add_to_watchlist(token_address, 'ethereum')
    
    assert result['token_address'] == token_address
    assert token_address in discovery_service._monitored_tokens

def test_remove_from_watchlist(discovery_service):
    token_address = "0x123..."
    discovery_service._monitored_tokens.add(token_address)
    
    # Test removing from watchlist
    assert discovery_service.remove_from_watchlist(token_address) is True
    assert token_address not in discovery_service._monitored_tokens
    
    # Test removing non-existent token
    assert discovery_service.remove_from_watchlist("0xabc...") is False

@pytest.mark.asyncio
async def test_update_discovery_config(discovery_service):
    new_config = {
        'min_liquidity': 15000,
        'min_holder_count': 75,
        'max_risk_score': 0.6
    }
    
    # Test config update
    updated = await discovery_service.update_discovery_config(new_config)
    
    assert float(updated['min_liquidity']) == 15000
    assert updated['min_holder_count'] == 75
    assert updated['max_risk_score'] == 0.6

@pytest.mark.asyncio
async def test_update_alert_thresholds(discovery_service):
    new_thresholds = {
        'price_change': 0.2,
        'volume_spike': 4.0
    }
    
    # Test threshold update
    updated = await discovery_service.update_alert_thresholds(new_thresholds)
    
    assert updated['price_change'] == 0.2
    assert updated['volume_spike'] == 4.0

# Handler Tests

@pytest.fixture
def mock_discovery():
    mock = AsyncMock()
    return mock

@pytest.fixture
def discovery_handler(mock_discovery):
    return TokenDiscoveryHandler(mock_discovery)

@pytest.mark.asyncio
async def test_discover_command(discovery_handler, mock_discovery):
    # Setup mock data
    mock_discovery.discover_tokens.return_value = [{
        'name': 'Test Token',
        'symbol': 'TEST',
        'token_address': '0x123...',
        'chain': 'ethereum',
        'liquidity': Decimal('20000'),
        'volume_24h': Decimal('10000'),
        'holder_count': 100,
        'risk_score': 0.5,
        'discovery_time': datetime.utcnow().isoformat(),
        'analysis': {
            'risk_factors': {'code_risk': 0.3}
        }
    }]
    
    # Test discover command
    result = await discovery_handler.discover_tokens('ethereum')
    
    assert 'New Trading Opportunities' in result
    assert 'Test Token (TEST)' in result
    assert '0x123...' in result

@pytest.mark.asyncio
async def test_monitor_command(discovery_handler, mock_discovery):
    # Setup mock data
    mock_discovery.monitor_tokens.return_value = [{
        'token_address': '0x123...',
        'chain': 'ethereum',
        'timestamp': datetime.utcnow().isoformat(),
        'changes': ['Price changed by 20%'],
        'current_data': {
            'price_usd': Decimal('2.0'),
            'liquidity': Decimal('20000'),
            'volume_24h': Decimal('10000'),
            'risk_score': 0.5
        }
    }]
    
    # Test monitor command
    result = await discovery_handler.monitor_tokens('ethereum')
    
    assert 'Token Monitoring Alerts' in result
    assert '0x123...' in result
    assert 'Price changed by 20%' in result

@pytest.mark.asyncio
async def test_watchlist_command(discovery_handler, mock_discovery):
    # Setup mock data for add
    mock_discovery.add_to_watchlist.return_value = {
        'token_address': '0x123...',
        'chain': 'ethereum',
        'added_time': datetime.utcnow().isoformat(),
        'analysis': {
            'name': 'Test Token',
            'symbol': 'TEST',
            'liquidity': Decimal('20000'),
            'volume_24h': Decimal('10000'),
            'holder_count': 100,
            'risk_score': 0.5
        }
    }
    
    # Test add to watchlist
    result = await discovery_handler.manage_watchlist(
        'add',
        '0x123...',
        'ethereum'
    )
    assert 'Added 0x123...' in result
    
    # Setup mock data for list
    mock_discovery.get_monitored_tokens.return_value = {'0x123...'}
    
    # Test list watchlist
    result = await discovery_handler.manage_watchlist('list')
    assert 'Token Watchlist' in result
    assert '0x123...' in result
    
    # Setup mock data for remove
    mock_discovery.remove_from_watchlist.return_value = True
    
    # Test remove from watchlist
    result = await discovery_handler.manage_watchlist(
        'remove',
        '0x123...'
    )
    assert 'Removed 0x123...' in result
