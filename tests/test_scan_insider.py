"""
Tests for scan and insider detection functionality
"""

import pytest
from datetime import datetime, timedelta
from handlers.settings import handle_settings_command
from handlers.scan import handle_scan_command, EnhancedDiscoveryScanner
from services.insider_detector import InsiderDetector
from db.models import get_db_manager

@pytest.fixture
def db():
    return get_db_manager()

@pytest.fixture
def scanner():
    return EnhancedDiscoveryScanner()

@pytest.fixture
def insider_detector():
    return InsiderDetector()

async def test_settings_crud(db):
    """Test settings CRUD operations"""
    user_id = 12345
    
    # Test setting values
    assert db.set_user_setting(user_id, "scan_min_score", "75")
    assert db.set_user_setting(user_id, "scan_max_results", "100")
    assert db.set_user_setting(user_id, "scan_chains", "eth,bsc")
    
    # Test getting values
    assert db.get_user_setting(user_id, "scan_min_score") == "75"
    assert db.get_user_setting(user_id, "scan_max_results") == "100"
    assert db.get_user_setting(user_id, "scan_chains") == "eth,bsc"

async def test_insider_detection(insider_detector):
    """Test insider detection scoring"""
    # Mock trade data
    trades = [
        {
            'timestamp': int((datetime.now() - timedelta(minutes=3)).timestamp()),
            'token_launch_time': int((datetime.now() - timedelta(minutes=5)).timestamp()),
            'profit_usd': 5000,
            'counterparty_is_dev': True
        },
        {
            'timestamp': int((datetime.now() - timedelta(minutes=4)).timestamp()),
            'token_launch_time': int((datetime.now() - timedelta(minutes=5)).timestamp()),
            'profit_usd': 3000,
            'counterparty_is_dev': False
        }
    ]
    
    # Test analysis
    result = await insider_detector.analyze('0xMockAddress', 'eth', lookback_minutes=5)
    
    # Verify scoring
    assert 'score' in result
    assert 'label' in result
    assert 'metrics' in result
    
    # Score should be high due to early entries and dev interaction
    assert result['score'] >= 70

async def test_scan_pagination(scanner):
    """Test scan pagination and result limiting"""
    user_id = 12345
    db = get_db_manager()
    
    # Set up test settings
    db.set_user_setting(user_id, "scan_max_results", "5")
    db.set_user_setting(user_id, "scan_min_score", "60")
    
    # Run scan
    results = await scanner.scan_with_settings(user_id)
    
    # Verify results
    assert len(results['results']) <= 5
    assert 'stats' in results
    assert 'total_scanned' in results['stats']
    assert 'passed_filters' in results['stats']

async def test_chain_filtering(scanner):
    """Test chain-specific scanning"""
    user_id = 12345
    db = get_db_manager()
    
    # Test ETH only
    db.set_user_setting(user_id, "scan_chains", "eth")
    results_eth = await scanner.scan_with_settings(user_id)
    assert all(r['chain'] == 'eth' for r in results_eth['results'])
    
    # Test BSC only
    db.set_user_setting(user_id, "scan_chains", "bsc")
    results_bsc = await scanner.scan_with_settings(user_id)
    assert all(r['chain'] == 'bsc' for r in results_bsc['results'])

async def test_insider_settings_integration(scanner):
    """Test insider settings integration with scan"""
    user_id = 12345
    db = get_db_manager()
    
    # Set strict insider detection
    db.set_user_setting(user_id, "insider_min_score", "90")
    db.set_user_setting(user_id, "insider_early_window_minutes", "2")
    db.set_user_setting(user_id, "insider_min_repeat", "5")
    
    results = await scanner.scan_with_settings(user_id)
    
    # Check insider flagging
    insider_results = [r for r in results['results'] if 'insider_score' in r]
    for result in insider_results:
        assert result['insider_score'] >= 90  # Should meet min_score
