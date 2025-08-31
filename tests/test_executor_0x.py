import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from executor import AdvancedTradeExecutor, ChainConfig
from config import Config
import json

class TestAdvancedTradeExecutor:
    """Test suite for AdvancedTradeExecutor"""
    
    @pytest.fixture
    def executor(self):
        """Create executor instance for testing"""
        return AdvancedTradeExecutor(chain_id=11155111)  # Sepolia testnet
    
    @pytest.fixture
    def sample_private_key(self):
        """Sample private key for testing (never use in production)"""
        return "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    
    @pytest.fixture
    def sample_quote(self):
        """Sample 0x quote response"""
        return {
            'price': '0.001234',
            'buyAmount': '1234567890123456789012',
            'sellAmount': '1000000000000000000',
            'estimatedGas': '150000',
            'gasPrice': '20000000000',
            'protocolFee': '0',
            'minimumProtocolFee': '0',
            'buyTokenAddress': '0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b',
            'sellTokenAddress': '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
            'allowanceTarget': '0xdef1c0ded9bec7f1a1670819833240f027b25eff',
            'to': '0xdef1c0ded9bec7f1a1670819833240f027b25eff',
            'data': '0x123456789...',
            'value': '1000000000000000000'
        }
    
    def test_executor_initialization(self, executor):
        """Test executor initializes correctly"""
        assert executor.chain_config.chain_id == 11155111
        assert executor.chain_config.name == 'sepolia'
        assert executor.web3 is not None
        assert hasattr(executor, 'eip1559_supported')
    
    @pytest.mark.asyncio
    async def test_get_0x_quote_success(self, executor, sample_quote):
        """Test successful 0x quote retrieval"""
        with patch('requests.get') as mock_get:
            # Mock successful API response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_quote
            mock_get.return_value = mock_response
            
            quote = await executor.get_0x_quote(
                sell_token='0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
                buy_token='0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b',
                sell_amount_wei=1000000000000000000  # 1 ETH
            )
            
            assert quote is not None
            assert 'price' in quote
            assert 'buyAmount' in quote
            assert 'estimatedGas' in quote
            assert quote['price'] == 0.001234
    
    @pytest.mark.asyncio
    async def test_get_0x_quote_retry_on_429(self, executor):
        """Test quote retry logic on rate limit"""
        with patch('requests.get') as mock_get, \
             patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            
            # First call returns 429, second returns success
            mock_response_429 = Mock()
            mock_response_429.status_code = 429
            
            mock_response_success = Mock()
            mock_response_success.status_code = 200
            mock_response_success.json.return_value = {'price': '0.001'}
            
            mock_get.side_effect = [mock_response_429, mock_response_success]
            
            quote = await executor.get_0x_quote(
                sell_token='0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
                buy_token='0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b',
                sell_amount_wei=1000000000000000000
            )
            
            # Should have retried and succeeded
            assert quote is not None
            assert mock_sleep.called
    
    @pytest.mark.asyncio
    async def test_prepare_0x_tx_dry_run(self, executor, sample_quote, sample_private_key):
        """Test transaction preparation in dry run mode"""
        with patch.object(executor.web3.eth, 'get_transaction_count', return_value=0), \
             patch.object(executor, 'check_and_approve_token', return_value=None), \
             patch.object(executor, 'add_gas_config') as mock_gas:
            
            # Mock gas configuration
            mock_gas.return_value = {
                'to': sample_quote['to'],
                'data': sample_quote['data'],
                'value': int(sample_quote['value']),
                'from': '0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b',
                'nonce': 0,
                'chainId': 11155111,
                'gas': 150000,
                'gasPrice': 20000000000
            }
            
            result = await executor.prepare_0x_tx(sample_quote, sample_private_key, dry_run=True)
            
            assert result is not None
            assert 'swap_tx' in result
            assert 'raw_transaction' in result['swap_tx']
            assert 'hash' in result['swap_tx']
            assert 'estimated_gas_cost' in result
    
    def test_calculate_gas_cost(self, executor):
        """Test gas cost calculation"""
        transaction = {
            'gas': 150000,
            'gasPrice': 20000000000  # 20 gwei
        }
        
        gas_cost = executor.calculate_gas_cost(transaction)
        
        # Should return cost in USD (placeholder calculation)
        assert gas_cost >= 0
        assert isinstance(gas_cost, float)
    
    @pytest.mark.asyncio
    async def test_add_gas_config_eip1559(self, executor):
        """Test EIP-1559 gas configuration"""
        if not executor.eip1559_supported:
            pytest.skip("EIP-1559 not supported on this network")
        
        transaction = {
            'from': '0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b',
            'to': '0xdef1c0ded9bec7f1a1670819833240f027b25eff',
            'data': '0x123456789'
        }
        
        with patch.object(executor.web3.eth, 'estimate_gas', return_value=150000), \
             patch.object(executor.web3.eth, 'get_block') as mock_get_block:
            
            # Mock latest block with base fee
            mock_block = Mock()
            mock_block.baseFeePerGas = 30000000000  # 30 gwei
            mock_get_block.return_value = mock_block
            
            result = await executor.add_gas_config(transaction)
            
            assert 'gas' in result
            assert 'maxFeePerGas' in result
            assert 'maxPriorityFeePerGas' in result
            assert result['gas'] > 150000  # Should include buffer
    
    @pytest.mark.asyncio
    async def test_add_gas_config_legacy(self, executor):
        """Test legacy gas configuration"""
        transaction = {
            'from': '0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b',
            'to': '0xdef1c0ded9bec7f1a1670819833240f027b25eff',
            'data': '0x123456789'
        }
        
        with patch.object(executor.web3.eth, 'estimate_gas', return_value=150000), \
             patch.object(executor.web3.eth, 'gas_price', 25000000000):  # 25 gwei
            
            # Force legacy mode
            original_eip1559 = executor.eip1559_supported
            executor.eip1559_supported = False
            
            try:
                result = await executor.add_gas_config(transaction)
                
                assert 'gas' in result
                assert 'gasPrice' in result
                assert 'maxFeePerGas' not in result
                assert result['gas'] > 150000  # Should include buffer
            finally:
                executor.eip1559_supported = original_eip1559
    
    @pytest.mark.asyncio
    async def test_check_and_approve_token_sufficient_allowance(self, executor, sample_private_key):
        """Test token approval when allowance is sufficient"""
        token_address = '0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b'
        spender = '0xdef1c0ded9bec7f1a1670819833240f027b25eff'
        amount = 1000000000000000000  # 1 token
        
        with patch.object(executor.web3.eth, 'contract') as mock_contract:
            # Mock contract with sufficient allowance
            mock_contract_instance = Mock()
            mock_contract_instance.functions.allowance.return_value.call.return_value = 2000000000000000000  # 2 tokens
            mock_contract.return_value = mock_contract_instance
            
            result = await executor.check_and_approve_token(
                token_address, spender, amount, sample_private_key, dry_run=True
            )
            
            # Should return None since no approval needed
            assert result is None
    
    @pytest.mark.asyncio
    async def test_execute_trade_success(self, executor, sample_quote, sample_private_key):
        """Test successful trade execution in dry run mode"""
        trade_params = {
            'user_id': 123456789,
            'sell_token': '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
            'buy_token': '0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b',
            'sell_amount_wei': 1000000000000000000,
            'private_key': sample_private_key,
            'slippage': 0.01,
            'dry_run': True
        }
        
        with patch.object(executor, 'get_0x_quote', return_value=sample_quote), \
             patch.object(executor, 'prepare_0x_tx') as mock_prepare, \
             patch.object(executor, 'create_trade_record', return_value={'trade_id': 'test_123'}):
            
            # Mock transaction preparation
            mock_prepare.return_value = {
                'swap_tx': {
                    'raw_transaction': '0x123456789...',
                    'hash': '0xabcdef123...'
                },
                'approval_tx': None,
                'estimated_gas_cost': 5.0,
                'quote': sample_quote
            }
            
            result = await executor.execute_trade(trade_params)
            
            assert result['success'] is True
            assert result['dry_run'] is True
            assert 'trade_id' in result
            assert 'transaction_hash' in result
            assert 'gas_cost_estimate' in result
    
    @pytest.mark.asyncio
    async def test_execute_trade_missing_params(self, executor):
        """Test trade execution with missing parameters"""
        incomplete_params = {
            'user_id': 123456789,
            'sell_token': '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'
            # Missing required parameters
        }
        
        result = await executor.execute_trade(incomplete_params)
        
        assert result['success'] is False
        assert 'error' in result
        assert 'Missing required parameter' in result['error']
    
    def test_chain_config_sepolia(self):
        """Test chain configuration for Sepolia"""
        config = ChainConfig(11155111)
        
        assert config.chain_id == 11155111
        assert config.name == 'sepolia'
        assert config.wrapped_native == Config.WETH_SEPOLIA
        assert config.router == Config.UNISWAP_V2_ROUTER
    
    def test_chain_config_bsc_testnet(self):
        """Test chain configuration for BSC testnet"""
        config = ChainConfig(97)
        
        assert config.chain_id == 97
        assert config.name == 'bsc-testnet'
        assert config.wrapped_native == Config.WBNB_TESTNET
        assert config.router == Config.PANCAKESWAP_ROUTER
    
    def test_chain_config_unsupported(self):
        """Test chain configuration for unsupported chain"""
        with pytest.raises(ValueError):
            ChainConfig(999999)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])