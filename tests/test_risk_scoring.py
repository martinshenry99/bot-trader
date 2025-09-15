"""
Tests for advanced risk scoring system
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta
from services.risk_scorer import RiskScorer, RiskMetrics

@pytest.fixture
def mock_apis():
    """Create mock APIs"""
    goplus_api = Mock()
    coingecko_api = Mock()
    
    # Mock security data
    goplus_api.get_token_security = AsyncMock(return_value={
        'is_contract_verified': True,
        'is_ownership_renounced': True,
        'is_proxy': False,
        'can_mint': False,
        'can_pause_trading': False,
        'is_honeypot': False,
        'has_transfer_restrictions': False,
        'has_blacklist': False,
        'has_antibot': False,
        'has_hidden_owner': False
    })
    
    # Mock market data
    coingecko_api.get_token_market_data = AsyncMock(return_value={
        'total_liquidity': '500000',
        'price_change_24h': '5.0',
        'volume_change_24h': '50.0',
        'price_impact_1000usd': '0.01',
        'market_cap': '1000000',
        'holder_distribution': {
            'top_10_share': 0.4
        },
        'days_since_launch': 90,
        'liquidity_pairs': ['USDT', 'USDC']
    })
    
    return goplus_api, coingecko_api

@pytest.mark.asyncio
async def test_low_risk_token(mock_apis):
    """Test scoring for a low-risk token"""
    goplus_api, coingecko_api = mock_apis
    scorer = RiskScorer(goplus_api, coingecko_api)
    
    metrics = await scorer.calculate_risk_score(
        token_address="0x123...",
        chain="ethereum"
    )
    
    assert metrics.overall_risk < 0.2
    assert len(metrics.risk_factors) == 0
    assert all(score < 0.3 for score in [
        metrics.token_score,
        metrics.liquidity_score,
        metrics.volatility_score,
        metrics.market_score,
        metrics.security_score
    ])

@pytest.mark.asyncio
async def test_high_risk_token(mock_apis):
    """Test scoring for a high-risk token"""
    goplus_api, coingecko_api = mock_apis
    
    # Update mock data for high risk scenario
    goplus_api.get_token_security = AsyncMock(return_value={
        'is_contract_verified': False,
        'is_ownership_renounced': False,
        'is_proxy': True,
        'can_mint': True,
        'can_pause_trading': True,
        'is_honeypot': False,
        'has_transfer_restrictions': True,
        'has_blacklist': True,
        'has_antibot': True,
        'has_hidden_owner': True
    })
    
    coingecko_api.get_token_market_data = AsyncMock(return_value={
        'total_liquidity': '5000',
        'price_change_24h': '60.0',
        'volume_change_24h': '250.0',
        'price_impact_1000usd': '0.08',
        'market_cap': '50000',
        'holder_distribution': {
            'top_10_share': 0.9
        },
        'days_since_launch': 2,
        'liquidity_pairs': ['USDT']
    })
    
    scorer = RiskScorer(goplus_api, coingecko_api)
    metrics = await scorer.calculate_risk_score(
        token_address="0x123...",
        chain="ethereum"
    )
    
    assert metrics.overall_risk > 0.7
    assert len(metrics.risk_factors) >= 5
    assert "Unverified contract" in metrics.risk_factors
    assert "Low liquidity" in metrics.risk_factors

@pytest.mark.asyncio
async def test_honeypot_detection(mock_apis):
    """Test honeypot detection"""
    goplus_api, coingecko_api = mock_apis
    
    # Set honeypot flag
    goplus_api.get_token_security = AsyncMock(return_value={
        'is_honeypot': True
    })
    
    scorer = RiskScorer(goplus_api, coingecko_api)
    metrics = await scorer.calculate_risk_score(
        token_address="0x123...",
        chain="ethereum"
    )
    
    assert metrics.security_score == 1.0
    assert metrics.overall_risk > 0.7
    assert "HONEYPOT DETECTED" in metrics.risk_factors

@pytest.mark.asyncio
async def test_risk_metrics_serialization():
    """Test RiskMetrics serialization"""
    metrics = RiskMetrics(
        token_score=0.5,
        liquidity_score=0.3,
        volatility_score=0.4,
        market_score=0.6,
        security_score=0.2,
        overall_risk=0.4,
        risk_factors=["Test factor 1", "Test factor 2"]
    )
    
    data = metrics.to_dict()
    assert isinstance(data, dict)
    assert len(data) == 7
    assert data['overall_risk'] == 0.4
    assert len(data['risk_factors']) == 2
    
    # Mock trading history
    mock_services['covalent'].get_wallet_history.return_value = [
        {
            'flip_time_minutes': 10,
            'profit_percentage': 20,
            'token_age_hours': 2
        },
        {
            'flip_time_minutes': 30,
            'profit_percentage': 15,
            'token_age_hours': 48
        }
    ]
    
    # Mock portfolio concentration
    mock_services['covalent'].get_token_balances.return_value = [
        Mock(usd_value=Decimal('1000')),
        Mock(usd_value=Decimal('500'))
    ]
    
    score = await risk_service.get_wallet_risk_score(wallet, chain)
    
    assert isinstance(score, RiskScore)
    assert 0 <= score.score <= 100
    assert isinstance(score.factors.owner_concentration, Decimal)
    assert isinstance(score.factors.insider_score, Decimal)

async def test_solana_chain_support(risk_service, mock_services):
    """Test Solana chain support"""
    token = "SoLTokenAddress"
    wallet = "SoLWalletAddress"
    chain = "solana"
    
    # Mock Helius responses
    mock_services['helius'].get_token_holders.return_value = Mock(
        top_holder_percentage=Decimal('30')
    )
    
    mock_services['helius'].get_wallet_history.return_value = [
        {
            'flip_time_minutes': 15,
            'profit_percentage': 25,
            'token_age_hours': 3
        }
    ]
    
    mock_services['helius'].get_token_accounts.return_value = [
        Mock(usd_value=Decimal('2000'))
    ]
    
    # Test token scoring
    with patch('core.secure_wallet.simulate_honeypot', return_value=False):
        with patch('core.secure_wallet.get_lp_info') as mock_lp:
            mock_lp.return_value = Mock(
                liquidity_usd=Decimal('75000'),
                is_locked=True
            )
            
            token_score = await risk_service.get_token_risk_score(token, chain)
            assert isinstance(token_score, RiskScore)
            assert token_score.chain == "solana"
    
    # Test wallet scoring
    wallet_score = await risk_service.get_wallet_risk_score(wallet, chain)
    assert isinstance(wallet_score, RiskScore)
    assert wallet_score.chain == "solana"

async def test_trading_pattern_analysis(risk_service):
    """Test trading pattern analysis"""
    history = [
        # Quick flip with large profit
        {
            'flip_time_minutes': 3,
            'profit_percentage': 60,
            'token_age_hours': 0.5
        },
        # Another quick flip
        {
            'flip_time_minutes': 4,
            'profit_percentage': 40,
            'token_age_hours': 0.75
        },
        # Normal trade
        {
            'flip_time_minutes': 120,
            'profit_percentage': 20,
            'token_age_hours': 48
        }
    ]
    
    analysis = risk_service._analyze_trading_patterns(history)
    
    assert 'Frequent quick flips' in analysis['suspicious_flags']
    assert analysis['insider_likelihood'] > 50

async def test_portfolio_concentration(risk_service, mock_services):
    """Test portfolio concentration calculation"""
    wallet = "0xwallet"
    chain = "ethereum"
    
    # Mock portfolio with high concentration
    mock_services['covalent'].get_token_balances.return_value = [
        Mock(usd_value=Decimal('8000')),  # 80% in one token
        Mock(usd_value=Decimal('2000'))
    ]
    
    concentration = await risk_service._get_portfolio_concentration(wallet, chain)
    assert concentration['concentration'] == Decimal('80')

def test_risk_score_weights():
    """Test risk score weight validation"""
    with pytest.raises(ValueError):
        RiskScoringService(
            Mock(),
            Mock(),
            Mock()
        ).weights.update({'honeypot': 50})  # Invalid weights sum

async def test_cache_behavior(risk_service, mock_services):
    """Test caching of risk scores"""
    token = "0xtoken"
    chain = "ethereum"
    
    # First call
    with patch('core.secure_wallet.simulate_honeypot', return_value=False):
        with patch('core.secure_wallet.get_lp_info') as mock_lp:
            mock_lp.return_value = Mock(
                liquidity_usd=Decimal('50000'),
                is_locked=True
            )
            
            score1 = await risk_service.get_token_risk_score(token, chain)
            
            # Second call should use cache
            score2 = await risk_service.get_token_risk_score(token, chain)
            
            assert score1.timestamp == score2.timestamp
            assert mock_lp.call_count == 1  # Should only be called once
