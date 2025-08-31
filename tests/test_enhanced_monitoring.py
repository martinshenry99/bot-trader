import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from monitor import MempoolMonitor, EnhancedTokenMonitor, EnhancedMonitoringManager
from datetime import datetime

class TestEnhancedMonitoring:
    """Test suite for enhanced monitoring functionality"""
    
    @pytest.fixture
    def mempool_monitor(self):
        """Create mempool monitor for testing"""
        return MempoolMonitor(chain_id=11155111)
    
    @pytest.fixture
    def token_monitor(self):
        """Create enhanced token monitor for testing"""
        return EnhancedTokenMonitor()
    
    @pytest.fixture
    def monitoring_manager(self):
        """Create enhanced monitoring manager for testing"""
        return EnhancedMonitoringManager()
    
    @pytest.fixture
    def sample_mempool_tx(self):
        """Sample mempool transaction"""
        return {
            'hash': '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
            'from': '0x742d35cc6ad5c87b7c2d3fa7f5c95ab3cde74d6b',
            'to': '0x7a250d5630b4cf539739df2c5dacb4c659f2488d',  # Uniswap router
            'input': '0x7ff36ab5000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000800000000000000000000000007420ed5c83747481a906a2c3b842e8a54',
            'value': '0x0de0b6b3a7640000',  # 1 ETH
            'gasPrice': '0x4a817c800',  # 20 gwei
            'gas': '0x249f0'  # ~150k gas
        }
    
    def test_mempool_monitor_initialization(self, mempool_monitor):
        """Test mempool monitor initializes correctly"""
        assert mempool_monitor.chain_id == 11155111
        assert mempool_monitor.is_running is False
        assert len(mempool_monitor.tracked_wallets) == 0
        assert len(mempool_monitor.tracked_tokens) == 0
        assert mempool_monitor.ws_url is not None
    
    @pytest.mark.asyncio
    async def test_mempool_monitor_start_stop(self, mempool_monitor):
        """Test starting and stopping mempool monitor"""
        test_wallets = ['0x742d35cc6ad5c87b7c2d3fa7f5c95ab3cde74d6b']
        test_tokens = ['0xa0b86a33e6441ba0bb7e1ae5e3e7baad5d1d7e3c']
        
        await mempool_monitor.start_mempool_monitoring(test_wallets, test_tokens)
        
        assert mempool_monitor.is_running is True
        assert len(mempool_monitor.tracked_wallets) == 1
        assert len(mempool_monitor.tracked_tokens) == 1
        
        await mempool_monitor.stop_mempool_monitoring()
        
        assert mempool_monitor.is_running is False
    
    @pytest.mark.asyncio
    async def test_process_mempool_message_tracked_wallet(self, mempool_monitor, sample_mempool_tx):
        """Test processing mempool message for tracked wallet"""
        # Add wallet to tracking
        test_wallet = '0x742d35cc6ad5c87b7c2d3fa7f5c95ab3cde74d6b'
        mempool_monitor.tracked_wallets.add(test_wallet)
        
        # Mock the processing methods
        with patch.object(mempool_monitor, 'process_tracked_wallet_swap') as mock_process:
            mock_process.return_value = None
            
            # Create websocket message
            message = json.dumps({
                'params': {
                    'result': sample_mempool_tx
                }
            })
            
            await mempool_monitor.process_mempool_message(message)
            
            # Should have called process_tracked_wallet_swap since it's a router interaction
            mock_process.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_decode_swap_transaction(self, mempool_monitor, sample_mempool_tx):
        """Test decoding swap transaction"""
        result = await mempool_monitor.decode_swap_transaction(sample_mempool_tx)
        
        assert result is not None
        assert 'method' in result
        assert result['method'] == 'swapExactETHForTokens'
        assert 'amount_in' in result
    
    @pytest.mark.asyncio
    async def test_create_mempool_alert(self, mempool_monitor):
        """Test creating mempool alert"""
        with patch('db.get_db_session') as mock_db_session:
            mock_db = Mock()
            mock_wallet = Mock()
            mock_wallet.user_id = 123456789
            mock_db.query.return_value.filter.return_value.first.return_value = mock_wallet
            mock_db_session.return_value = mock_db
            
            await mempool_monitor.create_mempool_alert(
                wallet_address='0x742d35cc6ad5c87b7c2d3fa7f5c95ab3cde74d6b',
                token_address='0xa0b86a33e6441ba0bb7e1ae5e3e7baad5d1d7e3c',
                transaction_hash='0x123456789...',
                swap_details={'method': 'swapExactETHForTokens'},
                usd_price=0.001
            )
            
            # Should have added alert to database
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
    
    def test_enhanced_token_monitor_initialization(self, token_monitor):
        """Test enhanced token monitor initialization"""
        assert token_monitor.is_running is False
        assert len(token_monitor.monitoring_tokens) == 0
        assert len(token_monitor.price_history) == 0
    
    @pytest.mark.asyncio
    async def test_enhanced_token_monitor_start_stop(self, token_monitor):
        """Test starting and stopping enhanced token monitor"""
        test_tokens = ['0x742d35cc6ad5c87b7c2d3fa7f5c95ab3cde74d6b']
        user_id = '123456789'
        
        await token_monitor.start_monitoring(test_tokens, user_id, price_threshold=0.10)
        
        assert token_monitor.is_running is True
        assert len(token_monitor.monitoring_tokens) == 1
        assert test_tokens[0] in token_monitor.monitoring_tokens
        assert token_monitor.monitoring_tokens[test_tokens[0]]['price_threshold'] == 0.10
        
        await token_monitor.stop_monitoring()
        
        assert token_monitor.is_running is False
        assert len(token_monitor.monitoring_tokens) == 0
    
    def test_analyze_price_trend(self, token_monitor):
        """Test price trend analysis"""
        token_address = '0x742d35cc6ad5c87b7c2d3fa7f5c95ab3cde74d6b'
        
        # Test with insufficient data
        token_monitor.price_history[token_address] = [
            {'price': 0.001, 'timestamp': datetime.utcnow()},
            {'price': 0.002, 'timestamp': datetime.utcnow()}
        ]
        
        trend = token_monitor.analyze_price_trend(token_address)
        assert trend == 'neutral'  # Not enough data
        
        # Test with bullish trend
        token_monitor.price_history[token_address] = [
            {'price': 0.001, 'timestamp': datetime.utcnow()},
            {'price': 0.002, 'timestamp': datetime.utcnow()},
            {'price': 0.003, 'timestamp': datetime.utcnow()},
            {'price': 0.004, 'timestamp': datetime.utcnow()},
            {'price': 0.005, 'timestamp': datetime.utcnow()}
        ]
        
        trend = token_monitor.analyze_price_trend(token_address)
        assert trend == 'bullish'
        
        # Test with bearish trend
        token_monitor.price_history[token_address] = [
            {'price': 0.005, 'timestamp': datetime.utcnow()},
            {'price': 0.004, 'timestamp': datetime.utcnow()},
            {'price': 0.003, 'timestamp': datetime.utcnow()},
            {'price': 0.002, 'timestamp': datetime.utcnow()},
            {'price': 0.001, 'timestamp': datetime.utcnow()}
        ]
        
        trend = token_monitor.analyze_price_trend(token_address)
        assert trend == 'bearish'
    
    @pytest.mark.asyncio
    async def test_enhanced_token_monitor_price_alert(self, token_monitor):
        """Test enhanced price alert creation"""
        token_address = '0x742d35cc6ad5c87b7c2d3fa7f5c95ab3cde74d6b'
        user_id = '123456789'
        
        with patch('db.get_db_session') as mock_db_session, \
             patch.object(token_monitor, 'update_token_in_db') as mock_update:
            
            mock_db = Mock()
            mock_token = Mock()
            mock_token.symbol = 'TEST'
            mock_db.query.return_value.filter.return_value.first.return_value = mock_token
            mock_db_session.return_value = mock_db
            
            await token_monitor.create_enhanced_price_alert(
                token_address, user_id, 15.5, 0.00115, 0.001, 'bullish', 'pump'
            )
            
            # Should have created alert
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_monitoring_manager_comprehensive_start(self, monitoring_manager):
        """Test starting comprehensive monitoring"""
        user_id = '123456789'
        config = {
            'tokens': ['0x742d35cc6ad5c87b7c2d3fa7f5c95ab3cde74d6b'],
            'wallets': ['0xa0b86a33e6441ba0bb7e1ae5e3e7baad5d1d7e3c'],
            'price_threshold': 0.05,
            'mempool_tracking': True
        }
        
        with patch.object(monitoring_manager.token_monitor, 'start_monitoring') as mock_token, \
             patch.object(monitoring_manager.wallet_monitor, 'start_monitoring') as mock_wallet, \
             patch.object(monitoring_manager.mempool_monitor, 'start_mempool_monitoring') as mock_mempool:
            
            await monitoring_manager.start_comprehensive_monitoring(user_id, config)
            
            # All monitors should have been started
            mock_token.assert_called_once_with(config['tokens'], user_id, 0.05)
            mock_wallet.assert_called_once_with(config['wallets'], user_id)
            mock_mempool.assert_called_once_with(config['wallets'], config['tokens'])
    
    @pytest.mark.asyncio
    async def test_monitoring_manager_status(self, monitoring_manager):
        """Test getting monitoring status"""
        # Mock running states
        monitoring_manager.token_monitor.is_running = True
        monitoring_manager.wallet_monitor.is_running = True
        monitoring_manager.mempool_monitor.is_running = False
        
        monitoring_manager.token_monitor.monitoring_tokens = {'token1': {}, 'token2': {}}
        monitoring_manager.wallet_monitor.monitoring_wallets = {'wallet1': {}}
        monitoring_manager.mempool_monitor.tracked_wallets = set(['wallet1'])
        monitoring_manager.mempool_monitor.tracked_tokens = set(['token1', 'token2'])
        
        status = await monitoring_manager.get_monitoring_status()
        
        assert status['token_monitor_running'] is True
        assert status['wallet_monitor_running'] is True
        assert status['mempool_monitor_running'] is False
        assert status['monitored_tokens'] == 2
        assert status['monitored_wallets'] == 1
        assert status['tracked_wallets_mempool'] == 1
        assert status['tracked_tokens_mempool'] == 2
    
    @pytest.mark.asyncio
    async def test_monitoring_manager_stop_all(self, monitoring_manager):
        """Test stopping all monitoring services"""
        with patch.object(monitoring_manager.token_monitor, 'stop_monitoring') as mock_token, \
             patch.object(monitoring_manager.wallet_monitor, 'stop_monitoring') as mock_wallet, \
             patch.object(monitoring_manager.mempool_monitor, 'stop_mempool_monitoring') as mock_mempool:
            
            await monitoring_manager.stop_all_monitoring()
            
            # All monitors should have been stopped
            mock_token.assert_called_once()
            mock_wallet.assert_called_once()
            mock_mempool.assert_called_once()

if __name__ == '__main__':
    pytest.main([__file__, '-v'])