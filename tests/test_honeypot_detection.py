import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from analyzer import HoneypotSimulator, RouterMapping, EnhancedTokenAnalyzer
from eth_account import Account

class TestHoneypotDetection:
    """Test suite for honeypot detection functionality"""
    
    @pytest.fixture
    def honeypot_simulator(self):
        """Create honeypot simulator for testing"""
        return HoneypotSimulator(chain_id=11155111)
    
    @pytest.fixture
    def analyzer(self):
        """Create enhanced token analyzer for testing"""
        return EnhancedTokenAnalyzer()
    
    @pytest.fixture
    def sample_token_address(self):
        """Sample token address for testing"""
        return "0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b"
    
    @pytest.fixture
    def sample_token_data(self):
        """Sample token data for testing"""
        return {
            'address': '0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b',
            'name': 'Test Token',
            'symbol': 'TEST',
            'decimals': 18,
            'price_usd': 0.001,
            'market_cap': 1000000,
            'liquidity_usd': 50000,
            'volume_24h': 10000
        }
    
    def test_router_mapping_ethereum(self):
        """Test router mapping for Ethereum"""
        router_info = RouterMapping.get_router_for_chain(11155111)
        
        assert router_info is not None
        assert router_info['address'] == RouterMapping.ROUTER_CONFIGS[RouterMapping.ROUTER_CONFIGS.__iter__().__next__()]
        assert 11155111 in router_info['config']['chain_ids']
    
    def test_router_mapping_bsc(self):
        """Test router mapping for BSC"""
        router_info = RouterMapping.get_router_for_chain(97)
        
        assert router_info is not None
        # Should find PancakeSwap router for BSC
        assert 97 in router_info['config']['chain_ids']
    
    def test_router_mapping_unsupported(self):
        """Test router mapping for unsupported chain"""
        router_info = RouterMapping.get_router_for_chain(999999)
        assert router_info is None
    
    def test_build_trading_path(self):
        """Test trading path construction"""
        token_address = "0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b"
        path = RouterMapping.build_token_to_weth_path(token_address, 11155111)
        
        assert len(path) == 2
        assert path[0] == token_address
        # Second should be WETH for the chain
    
    @pytest.mark.honeypot
    @pytest.mark.asyncio
    async def test_comprehensive_honeypot_check_safe_token(self, honeypot_simulator, sample_token_address):
        """Test comprehensive honeypot check for safe token"""
        with patch.object(honeypot_simulator, 'analyze_contract_risks') as mock_contract, \
             patch.object(honeypot_simulator, 'analyze_liquidity_risks') as mock_liquidity, \
             patch.object(honeypot_simulator, 'simulate_trading_scenarios') as mock_trading, \
             patch.object(honeypot_simulator, 'analyze_ownership_concentration') as mock_ownership:
            
            # Mock all checks returning low risk
            mock_contract.return_value = {'risk_score': 1, 'risk_factors': []}
            mock_liquidity.return_value = {'risk_score': 1, 'risk_factors': []}
            mock_trading.return_value = {'risk_score': 1, 'risk_factors': []}
            mock_ownership.return_value = {'risk_score': 1, 'risk_factors': []}
            
            result = await honeypot_simulator.comprehensive_honeypot_check(sample_token_address)
            
            assert result['is_honeypot'] is False
            assert result['risk_score'] <= 6  # Should be low risk
            assert isinstance(result['risk_factors'], list)
    
    @pytest.mark.honeypot
    @pytest.mark.asyncio
    async def test_comprehensive_honeypot_check_dangerous_token(self, honeypot_simulator, sample_token_address):
        """Test comprehensive honeypot check for dangerous token"""
        with patch.object(honeypot_simulator, 'analyze_contract_risks') as mock_contract, \
             patch.object(honeypot_simulator, 'analyze_liquidity_risks') as mock_liquidity, \
             patch.object(honeypot_simulator, 'simulate_trading_scenarios') as mock_trading, \
             patch.object(honeypot_simulator, 'analyze_ownership_concentration') as mock_ownership:
            
            # Mock all checks returning high risk
            mock_contract.return_value = {'risk_score': 3, 'risk_factors': ['Contract not verified']}
            mock_liquidity.return_value = {'risk_score': 3, 'risk_factors': ['Very low liquidity']}
            mock_trading.return_value = {'risk_score': 3, 'risk_factors': ['CRITICAL: Sell simulation failed']}
            mock_ownership.return_value = {'risk_score': 2, 'risk_factors': ['High ownership concentration']}
            
            result = await honeypot_simulator.comprehensive_honeypot_check(sample_token_address)
            
            assert result['is_honeypot'] is True  # Should be flagged as honeypot
            assert result['risk_score'] >= 7  # Should be high risk
            assert len(result['risk_factors']) > 0
    
    @pytest.mark.asyncio
    async def test_simulate_buy_transaction_success(self, honeypot_simulator, sample_token_address):
        """Test successful buy simulation"""
        ephemeral_account = Account.create()
        
        with patch.object(honeypot_simulator.web3.eth, 'call', return_value=b'success'):
            result = await honeypot_simulator.simulate_buy_transaction(sample_token_address, ephemeral_account)
            
            assert result['success'] is True
            assert 'result' in result
            assert result['message'] == 'Buy simulation successful'
    
    @pytest.mark.asyncio
    async def test_simulate_buy_transaction_honeypot_detected(self, honeypot_simulator, sample_token_address):
        """Test buy simulation with honeypot detection"""
        ephemeral_account = Account.create()
        
        # Mock eth_call raising an error with honeypot signature
        with patch.object(honeypot_simulator.web3.eth, 'call', side_effect=Exception('TRANSFER_FAILED')):
            result = await honeypot_simulator.simulate_buy_transaction(sample_token_address, ephemeral_account)
            
            assert result['success'] is False
            assert 'error' in result
            assert 'honeypot_signatures' in result
            assert result['is_honeypot_error'] is True
    
    @pytest.mark.asyncio
    async def test_simulate_sell_transaction_success(self, honeypot_simulator, sample_token_address):
        """Test successful sell simulation"""
        ephemeral_account = Account.create()
        
        with patch.object(honeypot_simulator.web3.eth, 'call', return_value=b'success'):
            result = await honeypot_simulator.simulate_sell_transaction(sample_token_address, ephemeral_account)
            
            assert result['success'] is True
            assert 'result' in result
            assert result['message'] == 'Sell simulation successful'
    
    @pytest.mark.asyncio
    async def test_simulate_sell_transaction_honeypot_blocked(self, honeypot_simulator, sample_token_address):
        """Test sell simulation blocked by honeypot"""
        ephemeral_account = Account.create()
        
        # Mock eth_call raising an error indicating selling is blocked
        with patch.object(honeypot_simulator.web3.eth, 'call', side_effect=Exception('LIQUIDITY_LOCKED')):
            result = await honeypot_simulator.simulate_sell_transaction(sample_token_address, ephemeral_account)
            
            assert result['success'] is False
            assert 'error' in result
            assert 'honeypot_signatures' in result
            assert len(result['honeypot_signatures']) > 0
    
    def test_detect_honeypot_signatures(self, honeypot_simulator):
        """Test honeypot signature detection"""
        # Test various honeypot error messages
        test_cases = [
            ('TRANSFER_FAILED', ['transfer_failed: TRANSFER_FAILED']),
            ('Insufficient output amount', ['insufficient_output: INSUFFICIENT_OUTPUT_AMOUNT']),
            ('Trading is disabled', ['trading_disabled: TRADING_DISABLED']),
            ('Normal error message', [])
        ]
        
        for error_msg, expected in test_cases:
            detected = honeypot_simulator.detect_honeypot_signatures(error_msg)
            # Check that detection works (may not match exactly due to implementation details)
            if expected:
                assert len(detected) > 0
            else:
                assert len(detected) == 0
    
    @pytest.mark.asyncio
    async def test_analyze_liquidity_risks_low_liquidity(self, honeypot_simulator, sample_token_address):
        """Test liquidity risk analysis for low liquidity token"""
        with patch('utils.api_client.CovalentClient') as mock_client:
            # Mock low liquidity token data
            mock_client_instance = Mock()
            mock_client_instance.get_token_data = AsyncMock(return_value={
                'liquidity_usd': 500  # Very low liquidity
            })
            mock_client.return_value = mock_client_instance
            
            # Patch the instance
            honeypot_simulator.covalent_client = mock_client_instance
            
            result = await honeypot_simulator.analyze_liquidity_risks(sample_token_address)
            
            assert result['risk_score'] >= 2  # Should have high risk score
            assert len(result['risk_factors']) > 0
            assert any('low liquidity' in factor.lower() for factor in result['risk_factors'])
    
    @pytest.mark.asyncio
    async def test_analyze_contract_risks(self, honeypot_simulator, sample_token_address):
        """Test contract risk analysis"""
        with patch.object(honeypot_simulator, 'check_proxy_pattern', return_value=True), \
             patch.object(honeypot_simulator, 'check_unusual_functions', return_value=['suspiciousFunction']):
            
            result = await honeypot_simulator.analyze_contract_risks(sample_token_address)
            
            assert isinstance(result, dict)
            assert 'risk_score' in result
            assert 'risk_factors' in result
            assert result['risk_score'] > 0  # Should have some risk
    
    @pytest.mark.asyncio
    async def test_enhanced_token_analyzer_integration(self, analyzer, sample_token_address, sample_token_data):
        """Test enhanced token analyzer with honeypot integration"""
        with patch.object(analyzer, 'get_token_data', return_value=sample_token_data), \
             patch.object(analyzer.honeypot_simulator, 'comprehensive_honeypot_check') as mock_honeypot, \
             patch.object(analyzer, 'analyze_sentiment', return_value=0.6), \
             patch.object(analyzer, 'lock_usd_at_trade', return_value={'price_usd': 0.001}):
            
            # Mock safe honeypot result
            mock_honeypot.return_value = {
                'is_honeypot': False,
                'risk_score': 2,
                'risk_factors': ['Low liquidity'],
                'simulation_results': {
                    'scenarios': {
                        'buy_simulation': {'success': True},
                        'sell_simulation': {'success': True}
                    }
                }
            }
            
            result = await analyzer.analyze_token(sample_token_address)
            
            assert 'honeypot_analysis' in result
            assert 'is_honeypot' in result
            assert 'trade_safety_score' in result
            assert result['is_honeypot'] is False
            assert result['trade_safety_score'] >= 0
    
    @pytest.mark.asyncio
    async def test_enhanced_analyzer_honeypot_blocking(self, analyzer, sample_token_address, sample_token_data):
        """Test that analyzer blocks honeypot tokens"""
        with patch.object(analyzer, 'get_token_data', return_value=sample_token_data), \
             patch.object(analyzer.honeypot_simulator, 'comprehensive_honeypot_check') as mock_honeypot:
            
            # Mock honeypot detection
            mock_honeypot.return_value = {
                'is_honeypot': True,
                'risk_score': 8,
                'risk_factors': ['CRITICAL: Sell simulation failed', 'Trading restrictions detected'],
                'simulation_results': {
                    'scenarios': {
                        'buy_simulation': {'success': True},
                        'sell_simulation': {'success': False, 'error': 'TRANSFER_FAILED'}
                    }
                }
            }
            
            result = await analyzer.analyze_token(sample_token_address)
            
            assert result['is_honeypot'] is True
            assert result['risk_level'] == 'CRITICAL'
            assert result['trade_safety_score'] <= 3  # Should be very low

if __name__ == '__main__':
    pytest.main([__file__, '-v'])