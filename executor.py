import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, List
from web3 import Web3
import requests
from config import Config
from db import get_db_session, Trade, User, Wallet

logger = logging.getLogger(__name__)

class TradeExecutor:
    """Execute trades on Ethereum (0x Protocol) - Testnet Only"""
    
    def __init__(self):
        self.web3 = Web3(Web3.HTTPProvider(Config.ETHEREUM_RPC_URL))
        # Note: POA middleware not needed for this implementation
        self.chain_id = Config.CHAIN_ID
        self.zeroex_api_url = "https://sepolia.api.0x.org"  # Sepolia testnet
        
    async def execute_trade(self, trade_params: Dict) -> Dict:
        """Execute a trade on 0x protocol"""
        try:
            logger.info(f"Executing trade: {trade_params}")
            
            # Validate trade parameters
            if not self.validate_trade_params(trade_params):
                raise ValueError("Invalid trade parameters")
            
            # Check wallet balance
            wallet_balance = await self.check_wallet_balance(
                trade_params['wallet_address'],
                trade_params['token_in_address']
            )
            
            if wallet_balance < trade_params['amount_in']:
                raise ValueError("Insufficient balance")
            
            # Get quote from 0x API
            quote = await self.get_0x_quote(trade_params)
            
            if not quote:
                raise ValueError("Failed to get trade quote")
            
            # Create trade record
            trade_record = await self.create_trade_record(trade_params, quote)
            
            # For testnet - simulate execution
            if Config.NETWORK_NAME == 'sepolia':
                result = await self.simulate_trade_execution(trade_params, quote, trade_record)
            else:
                result = await self.execute_real_trade(trade_params, quote, trade_record)
            
            # Update trade record with result
            await self.update_trade_record(trade_record['trade_id'], result)
            
            return {
                'success': True,
                'trade_id': trade_record['trade_id'],
                'tx_hash': result.get('tx_hash'),
                'gas_used': result.get('gas_used'),
                'amount_out': result.get('amount_out'),
                'execution_price': result.get('execution_price'),
                'message': 'Trade executed successfully'
            }
            
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Trade failed: {str(e)}'
            }
    
    def validate_trade_params(self, params: Dict) -> bool:
        """Validate trade parameters"""
        required_fields = [
            'user_id', 'wallet_address', 'trade_type',
            'token_in_address', 'token_out_address', 'amount_in'
        ]
        
        for field in required_fields:
            if field not in params:
                logger.error(f"Missing required parameter: {field}")
                return False
        
        # Validate addresses
        if not self.web3.is_address(params['wallet_address']):
            logger.error("Invalid wallet address")
            return False
        
        if not self.web3.is_address(params['token_in_address']):
            logger.error("Invalid token_in address")
            return False
            
        if not self.web3.is_address(params['token_out_address']):
            logger.error("Invalid token_out address")
            return False
        
        # Validate amount
        if params['amount_in'] <= 0:
            logger.error("Amount must be positive")
            return False
        
        return True
    
    async def check_wallet_balance(self, wallet_address: str, token_address: str) -> float:
        """Check wallet balance for a specific token"""
        try:
            # ETH balance check
            if token_address.lower() == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
                balance_wei = self.web3.eth.get_balance(wallet_address)
                return self.web3.from_wei(balance_wei, 'ether')
            
            # ERC20 token balance check
            erc20_abi = [
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "type": "function"
                }
            ]
            
            contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=erc20_abi
            )
            
            balance_raw = contract.functions.balanceOf(wallet_address).call()
            decimals = contract.functions.decimals().call()
            
            return balance_raw / (10 ** decimals)
            
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return 0.0
    
    async def get_0x_quote(self, trade_params: Dict) -> Optional[Dict]:
        """Get quote from 0x API"""
        try:
            # Build quote request
            quote_params = {
                'sellToken': trade_params['token_in_address'],
                'buyToken': trade_params['token_out_address'],
                'sellAmount': str(int(trade_params['amount_in'] * 1e18)),  # Convert to wei
                'slippagePercentage': trade_params.get('slippage', Config.DEFAULT_SLIPPAGE),
                'gasPrice': str(int(Config.MAX_GAS_PRICE * 1e9))  # Convert to wei
            }
            
            # Make API request
            response = requests.get(
                f"{self.zeroex_api_url}/swap/v1/quote",
                params=quote_params,
                timeout=Config.REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                quote_data = response.json()
                
                return {
                    'buy_amount': quote_data.get('buyAmount'),
                    'sell_amount': quote_data.get('sellAmount'),
                    'price': quote_data.get('price'),
                    'estimated_gas': quote_data.get('estimatedGas'),
                    'gas_price': quote_data.get('gasPrice'),
                    'protocol_fee': quote_data.get('protocolFee'),
                    'minimum_protocol_fee': quote_data.get('minimumProtocolFee'),
                    'buy_token_address': quote_data.get('buyTokenAddress'),
                    'sell_token_address': quote_data.get('sellTokenAddress'),
                    'allowance_target': quote_data.get('allowanceTarget'),
                    'to': quote_data.get('to'),
                    'data': quote_data.get('data')
                }
            else:
                logger.error(f"0x API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get 0x quote: {e}")
            return None
    
    async def create_trade_record(self, trade_params: Dict, quote: Dict) -> Dict:
        """Create trade record in database"""
        db = get_db_session()
        try:
            trade = Trade(
                user_id=trade_params['user_id'],
                wallet_address=trade_params['wallet_address'],
                token_address=trade_params['token_out_address'],
                trade_type=trade_params['trade_type'],
                amount_in=trade_params['amount_in'],
                amount_out=float(quote['buy_amount']) / 1e18,  # Convert from wei
                token_in_address=trade_params['token_in_address'],
                token_out_address=trade_params['token_out_address'],
                price_usd=trade_params.get('price_usd', 0),
                slippage=trade_params.get('slippage', Config.DEFAULT_SLIPPAGE),
                status='preparing'
            )
            
            db.add(trade)
            db.commit()
            db.refresh(trade)
            
            return {
                'trade_id': trade.trade_id,
                'id': trade.id
            }
            
        except Exception as e:
            logger.error(f"Failed to create trade record: {e}")
            raise
        finally:
            db.close()
    
    async def simulate_trade_execution(self, trade_params: Dict, quote: Dict, trade_record: Dict) -> Dict:
        """Simulate trade execution for testnet"""
        try:
            # Simulate execution delay
            await asyncio.sleep(2)
            
            # Generate mock transaction hash
            import hashlib
            import time
            mock_data = f"{trade_record['trade_id']}{time.time()}"
            tx_hash = "0x" + hashlib.sha256(mock_data.encode()).hexdigest()
            
            # Calculate simulated results
            amount_out = float(quote['buy_amount']) / 1e18
            gas_used = int(quote.get('estimated_gas', 150000))
            gas_price = float(quote.get('gas_price', 20)) / 1e9  # Convert to Gwei
            execution_price = amount_out / trade_params['amount_in'] if trade_params['amount_in'] > 0 else 0
            
            logger.info(f"✅ Simulated trade execution - TX: {tx_hash}")
            
            return {
                'tx_hash': tx_hash,
                'amount_out': amount_out,
                'gas_used': gas_used,
                'gas_price_gwei': gas_price,
                'execution_price': execution_price,
                'status': 'confirmed',
                'block_number': 12345678  # Mock block number
            }
            
        except Exception as e:
            logger.error(f"Trade simulation failed: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def execute_real_trade(self, trade_params: Dict, quote: Dict, trade_record: Dict) -> Dict:
        """Execute real trade (for mainnet - not implemented for safety)"""
        # This would contain real trade execution logic
        # For safety, this is not implemented in the demo
        raise NotImplementedError("Real trading not implemented for safety reasons")
    
    async def update_trade_record(self, trade_id: str, execution_result: Dict):
        """Update trade record with execution results"""
        db = get_db_session()
        try:
            trade = db.query(Trade).filter(Trade.trade_id == trade_id).first()
            if trade:
                trade.tx_hash = execution_result.get('tx_hash')
                trade.status = execution_result.get('status', 'failed')
                trade.gas_fee = execution_result.get('gas_used', 0) * execution_result.get('gas_price_gwei', 0) / 1e9
                trade.executed_at = datetime.utcnow()
                
                if 'amount_out' in execution_result:
                    trade.amount_out = execution_result['amount_out']
                
                db.commit()
                logger.info(f"Trade record updated: {trade_id}")
            
        except Exception as e:
            logger.error(f"Failed to update trade record: {e}")
        finally:
            db.close()
    
    async def get_trade_history(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get user trade history"""
        db = get_db_session()
        try:
            trades = db.query(Trade).filter(
                Trade.user_id == int(user_id)
            ).order_by(Trade.created_at.desc()).limit(limit).all()
            
            trade_history = []
            for trade in trades:
                trade_history.append({
                    'trade_id': trade.trade_id,
                    'trade_type': trade.trade_type,
                    'token_address': trade.token_address,
                    'amount_in': trade.amount_in,
                    'amount_out': trade.amount_out,
                    'price_usd': trade.price_usd,
                    'status': trade.status,
                    'tx_hash': trade.tx_hash,
                    'gas_fee': trade.gas_fee,
                    'created_at': trade.created_at.isoformat(),
                    'executed_at': trade.executed_at.isoformat() if trade.executed_at else None
                })
            
            return trade_history
            
        except Exception as e:
            logger.error(f"Failed to get trade history: {e}")
            return []
        finally:
            db.close()
    
    async def cancel_trade(self, trade_id: str, user_id: str) -> Dict:
        """Cancel pending trade"""
        db = get_db_session()
        try:
            trade = db.query(Trade).filter(
                Trade.trade_id == trade_id,
                Trade.user_id == int(user_id),
                Trade.status == 'pending'
            ).first()
            
            if not trade:
                return {'success': False, 'message': 'Trade not found or cannot be cancelled'}
            
            trade.status = 'cancelled'
            db.commit()
            
            return {'success': True, 'message': 'Trade cancelled successfully'}
            
        except Exception as e:
            logger.error(f"Failed to cancel trade: {e}")
            return {'success': False, 'message': f'Failed to cancel trade: {str(e)}'}
        finally:
            db.close()

class TradingStrategies:
    """Automated trading strategies"""
    
    def __init__(self):
        self.executor = TradeExecutor()
    
    async def dollar_cost_averaging(self, params: Dict) -> Dict:
        """Implement DCA strategy"""
        # Placeholder for DCA implementation
        return {'strategy': 'dca', 'status': 'not_implemented'}
    
    async def momentum_trading(self, params: Dict) -> Dict:
        """Implement momentum trading strategy"""
        # Placeholder for momentum trading
        return {'strategy': 'momentum', 'status': 'not_implemented'}
    
    async def arbitrage_detection(self, token_address: str) -> List[Dict]:
        """Detect arbitrage opportunities"""
        # Placeholder for arbitrage detection
        return []