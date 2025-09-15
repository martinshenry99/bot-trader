"""
Tests for insider trading detection
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
import networkx as nx
from services.insider_detector import InsiderDetector, InsiderScore, InsiderSignal

@pytest.fixture
def mock_services():
    """Mock external service dependencies"""
    return {
        'covalent': AsyncMock(),
        'helius': AsyncMock()
    }

@pytest.fixture
def insider_detector(mock_services):
    """Create insider detector with mocked services"""
    return InsiderDetector(
        mock_services['covalent'],
        mock_services['helius']
    )

@pytest.fixture
def sample_history():
    """Sample trading history"""
    now = datetime.now()
    return [
        {
            'token_age_minutes': 15,
            'profit_percentage': 120,
            'from_address': '0xwallet',
            'to_address': '0xtrader1',
            'timestamp': int((now - timedelta(days=1)).timestamp())
        },
        {
            'token_age_minutes': 25,
            'profit_percentage': 150,
            'from_address': '0xwallet',
            'to_address': '0xtrader2',
            'timestamp': int((now - timedelta(days=2)).timestamp())
        },
        {
            'token_age_minutes': 120,
            'profit_percentage': 30,
            'from_address': '0xtrader1',
            'to_address': '0xwallet',
            'timestamp': int((now - timedelta(days=3)).timestamp())
        }
    ]

async def test_wallet_analysis(insider_detector, mock_services, sample_history):
    """Test comprehensive wallet analysis"""
    wallet = "0xwallet"
    chain = "ethereum"
    
    # Mock service responses
    mock_services['covalent'].get_wallet_history.return_value = sample_history
    mock_services['covalent'].get_token_deployments.return_value = [
        {'deployer': '0xdeployer1'},
        {'deployer': '0xdeployer2'}
    ]
    mock_services['covalent'].find_wallet_path.return_value = ['0xwallet', '0xmiddle', '0xdeployer1']
    mock_services['covalent'].get_token_transfers.return_value = [
        {'from_new_wallet': True},
        {'mixed_funds': True}
    ]
    
    # Analyze wallet
    score = await insider_detector.analyze_wallet(wallet, chain)
    
    assert isinstance(score, InsiderScore)
    assert 0 <= score.score <= 100
    assert isinstance(score.wallet_cluster, set)
    assert 0 <= score.deployer_proximity <= 1
    assert 0 <= score.early_trading_score <= 1
    assert all(isinstance(s, InsiderSignal) for s in score.signals)

async def test_deployer_proximity(insider_detector, mock_services):
    """Test deployer proximity calculation"""
    wallet = "0xwallet"
    chain = "ethereum"
    
    # Mock deployments and paths
    mock_services['covalent'].get_token_deployments.return_value = [
        {'deployer': '0xdeployer1'},
        {'deployer': '0xdeployer2'}
    ]
    
    # Test direct connection
    mock_services['covalent'].find_wallet_path.return_value = ['0xwallet', '0xdeployer1']
    prox1 = await insider_detector._check_deployer_proximity(wallet, chain)
    assert prox1 > 0.8  # Should be high for direct connection
    
    # Test distant connection
    mock_services['covalent'].find_wallet_path.return_value = ['0xwallet', 'x', 'y', 'z', '0xdeployer1']
    prox2 = await insider_detector._check_deployer_proximity(wallet, chain)
    assert prox2 < 0.5  # Should be lower for distant connection
    
    # Test no connection
    mock_services['covalent'].find_wallet_path.return_value = None
    prox3 = await insider_detector._check_deployer_proximity(wallet, chain)
    assert prox3 == 0.0

def test_early_trading_analysis(insider_detector):
    """Test early trading pattern analysis"""
    # Create sample histories
    high_risk = [
        {'token_age_minutes': 10, 'profit_percentage': 200},
        {'token_age_minutes': 15, 'profit_percentage': 150},
        {'token_age_minutes': 20, 'profit_percentage': 120}
    ]
    
    low_risk = [
        {'token_age_minutes': 120, 'profit_percentage': 20},
        {'token_age_minutes': 180, 'profit_percentage': 30},
        {'token_age_minutes': 240, 'profit_percentage': 15}
    ]
    
    score_high = insider_detector._analyze_early_trading(high_risk)
    score_low = insider_detector._analyze_early_trading(low_risk)
    
    assert score_high > 0.7  # Should detect early profitable trading
    assert score_low < 0.3  # Should be low for normal trading

def test_repeated_multipliers(insider_detector):
    """Test repeated multiplier detection"""
    # Create sample histories
    suspicious = [
        {'profit_percentage': 150},
        {'profit_percentage': 200},
        {'profit_percentage': 180},
        {'profit_percentage': 20}
    ]
    
    normal = [
        {'profit_percentage': 30},
        {'profit_percentage': 25},
        {'profit_percentage': 40},
        {'profit_percentage': 20}
    ]
    
    score_suspicious = insider_detector._check_repeated_multipliers(suspicious)
    score_normal = insider_detector._check_repeated_multipliers(normal)
    
    assert score_suspicious > 0.6  # Should detect repeated high profits
    assert score_normal < 0.3  # Should be low for normal profits

async def test_trading_cluster(insider_detector, mock_services):
    """Test trading cluster detection"""
    wallet = "0xwallet"
    chain = "ethereum"
    
    # Create connected trading history
    history = [
        {'from_address': wallet, 'to_address': '0xtrader1'},
        {'from_address': '0xtrader1', 'to_address': '0xtrader2'},
        {'from_address': '0xtrader2', 'to_address': '0xtrader3'},
        {'from_address': '0xtrader3', 'to_address': wallet}
    ]
    
    mock_services['covalent'].get_wallet_history.return_value = history
    
    cluster = await insider_detector._get_trading_cluster(wallet, chain)
    
    assert len(cluster) >= insider_detector.settings['min_cluster_size']
    assert wallet in cluster
    assert '0xtrader1' in cluster

async def test_suspicious_inflows(insider_detector, mock_services):
    """Test suspicious inflow detection"""
    wallet = "0xwallet"
    chain = "ethereum"
    
    # Create suspicious transfers
    transfers = [
        {'from_new_wallet': True, 'mixed_funds': False},
        {'from_new_wallet': False, 'mixed_funds': True},
        {'tornado_cash_proximity': True},
        {'from_new_wallet': False, 'mixed_funds': False}
    ]
    
    mock_services['covalent'].get_token_transfers.return_value = transfers
    
    score = await insider_detector._check_suspicious_inflows(wallet, chain)
    
    assert score > 0.5  # Should detect suspicious patterns
    assert score <= 1.0  # Should be normalized

def test_insider_score_calculation(insider_detector):
    """Test final insider score calculation"""
    # Create sample signals
    signals = [
        InsiderSignal(
            wallet="0xwallet",
            signal_type="deployer_proximity",
            confidence=0.8,
            evidence={"distance": 1},
            timestamp=int(datetime.now().timestamp())
        ),
        InsiderSignal(
            wallet="0xwallet",
            signal_type="early_trading",
            confidence=0.9,
            evidence={"score": 0.9},
            timestamp=int(datetime.now().timestamp())
        )
    ]
    
    score = insider_detector._calculate_insider_score(
        signals,
        deployer_prox=0.8,
        early_score=0.9
    )
    
    assert isinstance(score, float)
    assert 60 <= score <= 100  # Should be high for strong signals

async def test_solana_chain_support(insider_detector, mock_services):
    """Test Solana chain support"""
    wallet = "SolanaWallet"
    chain = "solana"
    
    # Mock Helius responses
    mock_services['helius'].get_wallet_history.return_value = [
        {'token_age_minutes': 10, 'profit_percentage': 150}
    ]
    mock_services['helius'].get_token_deployments.return_value = [
        {'deployer': 'SolDeployer1'}
    ]
    mock_services['helius'].find_wallet_path.return_value = ['SolanaWallet', 'SolDeployer1']
    
    score = await insider_detector.analyze_wallet(wallet, chain)
    
    assert isinstance(score, InsiderScore)
    # Verify Helius was used instead of Covalent
    assert mock_services['helius'].get_wallet_history.called
    assert not mock_services['covalent'].get_wallet_history.called

def test_cache_behavior(insider_detector):
    """Test caching of wallet distance calculations"""
    wallet1 = "0xwallet1"
    wallet2 = "0xwallet2"
    chain = "ethereum"
    
    # First call
    with patch('services.insider_detector.InsiderDetector._calculate_wallet_distance') as mock_calc:
        mock_calc.return_value = 2
        distance1 = insider_detector._calculate_wallet_distance(wallet1, wallet2, chain)
        
        # Second call should use cache
        distance2 = insider_detector._calculate_wallet_distance(wallet1, wallet2, chain)
        
        assert mock_calc.call_count == 1  # Should only calculate once
