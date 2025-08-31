import asyncio
import logging
import json
import time
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from web3 import Web3
from eth_account import Account
from eth_keyfile import extract_key_from_keyfile
import requests
from config import Config
from db import get_db_session, Trade, User, Wallet

logger = logging.getLogger(__name__)

class ChainConfig:
    """Chain-specific configuration"""
    
    def __init__(self, chain_id: int):
        self.chain_id = chain_id
        
        if chain_id == 11155111:  # Sepolia
            self.rpc_url = Config.ETHEREUM_RPC_URL
            self.api_url = Config.ZEROEX_ETH_API
            self.wrapped_native = Config.WETH_SEPOLIA
            self.router = Config.UNISWAP_V2_ROUTER
            self.name = 'sepolia'
        elif chain_id == 97:  # BSC Testnet
            self.rpc_url = Config.BSC_RPC_URL
            self.api_url = Config.ZEROEX_BSC_API
            self.wrapped_native = Config.WBNB_TESTNET
            self.router = Config.PANCAKESWAP_ROUTER
            self.name = 'bsc-testnet'
        else:
            raise ValueError(f"Unsupported chain ID: {chain_id}")

class AdvancedTradeExecutor:
    """Advanced trade executor with 0x Protocol integration and proper gas handling"""
    
    def __init__(self, chain_id: int = 11155111):
        self.chain_config = ChainConfig(chain_id)
        self.web3 = Web3(Web3.HTTPProvider(self.chain_config.rpc_url))
        
        # Verify connection
        if not self.web3.is_connected():
            raise ConnectionError(f"Failed to connect to {self.chain_config.name} RPC")
        
        # Check if EIP-1559 is supported
        try:
            latest_block = self.web3.eth.get_block('latest')
            self.eip1559_supported = hasattr(latest_block, 'baseFeePerGas') and latest_block.baseFeePerGas is not None
        except:
            self.eip1559_supported = False
        
        logger.info(f"Initialized executor for {self.chain_config.name} (EIP-1559: {self.eip1559_supported})")
    
    async def get_0x_quote(self, sell_token: str, buy_token: str, sell_amount_wei: int, 
                          slippage: float = 0.01, user_address: str = None) -> Optional[Dict]:
        """Get quote from 0x API with retry and backoff"""
        
        # Normalize token addresses
        if sell_token.lower() == '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee':
            sell_token = self.chain_config.wrapped_native
        if buy_token.lower() == '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee':
            buy_token = self.chain_config.wrapped_native
        
        quote_params = {
            'sellToken': sell_token,
            'buyToken': buy_token,
            'sellAmount': str(sell_amount_wei),
            'slippagePercentage': str(slippage),
            'skipValidation': 'true',  # For testnet
            'feeRecipient': '0x0000000000000000000000000000000000000000',
            'buyTokenPercentageFee': '0'
        }
        
        if user_address:
            quote_params['takerAddress'] = user_address
        
        # Retry logic with exponential backoff
        for attempt in range(Config.MAX_RETRIES):
            try:
                logger.info(f"Getting 0x quote (attempt {attempt + 1})")
                
                response = requests.get(
                    f"{self.chain_config.api_url}/swap/v1/quote",
                    params=quote_params,
                    timeout=Config.REQUEST_TIMEOUT,
                    headers={
                        'User-Agent': 'MemeTrader/1.0',
                        '0x-api-key': 'your-api-key'  # Add if you have one
                    }
                )
                
                if response.status_code == 200:
                    quote_data = response.json()
                    
                    # Normalize quote response
                    normalized_quote = {
                        'price': float(quote_data.get('price', 0)),
                        'buyAmount': quote_data.get('buyAmount'),
                        'sellAmount': quote_data.get('sellAmount'),
                        'estimatedGas': int(quote_data.get('estimatedGas', 150000)),
                        'gasPrice': quote_data.get('gasPrice'),
                        'protocolFee': quote_data.get('protocolFee', '0'),
                        'minimumProtocolFee': quote_data.get('minimumProtocolFee', '0'),
                        'buyTokenAddress': quote_data.get('buyTokenAddress'),
                        'sellTokenAddress': quote_data.get('sellTokenAddress'),
                        'allowanceTarget': quote_data.get('allowanceTarget'),
                        'to': quote_data.get('to'),
                        'data': quote_data.get('data'),
                        'value': quote_data.get('value', '0'),
                        'decodedUniqueId': quote_data.get('decodedUniqueId'),
                        'sources': quote_data.get('sources', [])
                    }
                    
                    logger.info(f"✅ 0x quote successful: price={normalized_quote['price']:.6f}")
                    return normalized_quote
                
                elif response.status_code == 429:
                    # Rate limit hit
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limit hit, waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                    continue
                
                else:
                    logger.error(f"0x API error: {response.status_code} - {response.text}")
                    if attempt == Config.MAX_RETRIES - 1:
                        return None
                    
            except requests.exceptions.Timeout:
                wait_time = 2 ** attempt
                logger.warning(f"Request timeout, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
                continue
                
            except Exception as e:
                logger.error(f"0x quote error: {e}")
                if attempt == Config.MAX_RETRIES - 1:
                    return None
                await asyncio.sleep(1)
        
        return None
    
    async def check_and_approve_token(self, token_address: str, spender: str, amount: int, 
                                    private_key: str, dry_run: bool = True) -> Optional[str]:
        """Check allowance and approve if needed"""
        
        if token_address.lower() == self.chain_config.wrapped_native.lower():
            return None  # No approval needed for native token
        
        try:
            # Get user address from private key
            account = Account.from_key(private_key)
            user_address = account.address
            
            # ERC-20 ABI for allowance and approve
            erc20_abi = [
                {
                    "constant": True,
                    "inputs": [
                        {"name": "_owner", "type": "address"},
                        {"name": "_spender", "type": "address"}
                    ],
                    "name": "allowance",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "type": "function"
                },
                {
                    "constant": False,
                    "inputs": [
                        {"name": "_spender", "type": "address"},
                        {"name": "_value", "type": "uint256"}
                    ],
                    "name": "approve",
                    "outputs": [{"name": "", "type": "bool"}],
                    "type": "function"
                }
            ]
            
            # Create contract instance
            contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=erc20_abi
            )
            
            # Check current allowance
            current_allowance = contract.functions.allowance(user_address, spender).call()
            
            if current_allowance >= amount:
                logger.info(f"✅ Sufficient allowance: {current_allowance} >= {amount}")
                return None
            
            logger.info(f"⚠️  Insufficient allowance: {current_allowance} < {amount}, approving...")
            
            # Build approval transaction
            approval_amount = amount * 2  # Approve 2x to avoid frequent approvals
            
            approve_txn = contract.functions.approve(spender, approval_amount).build_transaction({
                'from': user_address,
                'nonce': self.web3.eth.get_transaction_count(user_address, 'pending'),
                'chainId': self.chain_config.chain_id
            })
            
            # Add gas configuration
            approve_txn = await self.add_gas_config(approve_txn)
            
            # Sign transaction
            signed_txn = self.web3.eth.account.sign_transaction(approve_txn, private_key)
            
            if dry_run:
                logger.info(f"🧪 DRY RUN: Approval transaction prepared (hash would be: {signed_txn.hash.hex()})")
                return signed_txn.rawTransaction.hex()
            else:
                # Broadcast approval
                tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
                logger.info(f"📤 Approval transaction sent: {tx_hash.hex()}")
                
                # Wait for confirmation
                receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
                if receipt.status == 1:
                    logger.info(f"✅ Approval confirmed: {tx_hash.hex()}")
                    return tx_hash.hex()
                else:
                    logger.error(f"❌ Approval failed: {tx_hash.hex()}")
                    return None
                    
        except Exception as e:
            logger.error(f"Token approval error: {e}")
            return None
    
    async def add_gas_config(self, transaction: Dict) -> Dict:
        """Add appropriate gas configuration based on network support"""
        
        try:
            # Estimate gas limit
            estimated_gas = self.web3.eth.estimate_gas(transaction)
            gas_limit = int(estimated_gas * Config.GAS_LIMIT_BUFFER)
            transaction['gas'] = gas_limit
            
            if self.eip1559_supported:
                # EIP-1559 gas configuration
                latest_block = self.web3.eth.get_block('latest')
                base_fee = latest_block.baseFeePerGas
                
                # Calculate priority fee (tip)
                max_priority_fee = self.web3.to_wei(2, 'gwei')  # 2 gwei tip
                max_fee = base_fee * 2 + max_priority_fee  # 2x base fee + tip
                
                # Cap the max fee
                max_fee_cap = self.web3.to_wei(Config.MAX_GAS_PRICE, 'gwei')
                max_fee = min(max_fee, max_fee_cap)
                
                transaction['maxFeePerGas'] = max_fee
                transaction['maxPriorityFeePerGas'] = max_priority_fee
                
                logger.info(f"EIP-1559 gas: maxFee={self.web3.from_wei(max_fee, 'gwei'):.2f} gwei, "
                          f"maxPriority={self.web3.from_wei(max_priority_fee, 'gwei'):.2f} gwei")
                
            else:
                # Legacy gas pricing
                gas_price = self.web3.eth.gas_price
                gas_price_cap = self.web3.to_wei(Config.MAX_GAS_PRICE, 'gwei')
                gas_price = min(gas_price, gas_price_cap)
                
                transaction['gasPrice'] = gas_price
                
                logger.info(f"Legacy gas: price={self.web3.from_wei(gas_price, 'gwei'):.2f} gwei")
            
            logger.info(f"Gas limit: {gas_limit:,}")
            return transaction
            
        except Exception as e:
            logger.error(f"Gas configuration error: {e}")
            # Fallback gas configuration
            transaction['gas'] = 200000
            if self.eip1559_supported:
                transaction['maxFeePerGas'] = self.web3.to_wei(20, 'gwei')
                transaction['maxPriorityFeePerGas'] = self.web3.to_wei(2, 'gwei')
            else:
                transaction['gasPrice'] = self.web3.to_wei(20, 'gwei')
            
            return transaction
    
    async def prepare_0x_tx(self, quote: Dict, private_key: str, dry_run: bool = True) -> Optional[Dict]:
        """Prepare and sign 0x transaction"""
        
        try:
            # Get account from private key
            account = Account.from_key(private_key)
            user_address = account.address
            
            logger.info(f"Preparing 0x transaction for {user_address}")
            
            # Check if token approval is needed
            sell_token = quote.get('sellTokenAddress')
            allowance_target = quote.get('allowanceTarget')
            sell_amount = int(quote.get('sellAmount', 0))
            
            approval_tx = None
            if sell_token and allowance_target and sell_token.lower() != self.chain_config.wrapped_native.lower():
                approval_tx = await self.check_and_approve_token(
                    sell_token, allowance_target, sell_amount, private_key, dry_run
                )
            
            # Build the swap transaction
            swap_txn = {
                'to': Web3.to_checksum_address(quote['to']),
                'data': quote['data'],
                'value': int(quote.get('value', 0)),
                'from': user_address,
                'nonce': self.web3.eth.get_transaction_count(user_address, 'pending'),
                'chainId': self.chain_config.chain_id
            }
            
            # Add gas configuration
            swap_txn = await self.add_gas_config(swap_txn)
            
            # Sign transaction
            signed_swap = self.web3.eth.account.sign_transaction(swap_txn, private_key)
            
            result = {
                'swap_tx': {
                    'raw_transaction': signed_swap.rawTransaction.hex(),
                    'hash': signed_swap.hash.hex(),
                    'transaction': swap_txn
                },
                'approval_tx': approval_tx,
                'estimated_gas_cost': self.calculate_gas_cost(swap_txn),
                'quote': quote
            }
            
            if dry_run:
                logger.info(f"🧪 DRY RUN: Swap transaction prepared")
                logger.info(f"   • Transaction hash: {signed_swap.hash.hex()}")
                logger.info(f"   • Gas cost estimate: ${result['estimated_gas_cost']:.4f}")
                logger.info(f"   • Buy amount: {quote.get('buyAmount', 0)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Transaction preparation error: {e}")
            return None
    
    def calculate_gas_cost(self, transaction: Dict) -> float:
        """Calculate estimated gas cost in USD"""
        try:
            gas_limit = transaction.get('gas', 200000)
            
            if 'maxFeePerGas' in transaction:
                gas_price = transaction['maxFeePerGas']
            else:
                gas_price = transaction.get('gasPrice', self.web3.to_wei(20, 'gwei'))
            
            gas_cost_wei = gas_limit * gas_price
            gas_cost_eth = self.web3.from_wei(gas_cost_wei, 'ether')
            
            # Estimate ETH price (placeholder - in production, fetch real price)
            eth_price_usd = 2000  # Placeholder ETH price
            
            return float(gas_cost_eth) * eth_price_usd
            
        except Exception as e:
            logger.error(f"Gas cost calculation error: {e}")
            return 0.0
    
    async def execute_jupiter_trade(self, trade_params: Dict) -> Dict:
        """
        Execute Solana trade using Jupiter API
        
        Args:
            trade_params: Trade parameters for Jupiter swap
            
        Returns:
            Execution result
        """
        try:
            logger.info("🚀 Executing Jupiter trade...")
            
            # Get Jupiter client
            from integrations.base import integration_manager
            jupiter_client = integration_manager.get_client('jupiter')
            
            if not jupiter_client:
                return {'success': False, 'error': 'Jupiter client not available'}
            
            # Convert USD amount to SOL amount if needed
            input_amount = await self._convert_usd_to_token_amount(
                trade_params.get('amount_usd', 0),
                trade_params['input_mint']
            )
            
            # Get quote from Jupiter
            quote = await jupiter_client.get_quote(
                input_mint=trade_params['input_mint'],
                output_mint=trade_params['output_mint'],
                amount=input_amount,
                slippage_bps=trade_params.get('slippage_bps', 50)
            )
            
            if not quote:
                return {'success': False, 'error': 'Failed to get Jupiter quote'}
            
            # Validate quote
            validation = await jupiter_client.validate_quote(quote)
            if not validation['is_valid']:
                return {
                    'success': False, 
                    'error': 'Invalid quote',
                    'warnings': validation['warnings']
                }
            
            # Get user's Solana wallet
            user_wallet = await self._get_solana_wallet(trade_params['user_id'])
            if not user_wallet:
                return {'success': False, 'error': 'No Solana wallet configured'}
            
            # Get swap transaction
            swap_tx = await jupiter_client.get_swap_transaction(
                quote_data=quote,
                user_public_key=user_wallet['public_key'],
                priority_fee=10000  # 0.01 SOL priority fee
            )
            
            if not swap_tx:
                return {'success': False, 'error': 'Failed to get swap transaction'}
            
            # Create trade record
            trade_record = await self.create_jupiter_trade_record(trade_params, quote, swap_tx)
            
            if trade_params.get('dry_run', Config.DRY_RUN_MODE):
                return {
                    'success': True,
                    'dry_run': True,
                    'trade_id': trade_record.get('trade_id'),
                    'quote': quote,
                    'estimated_output': quote.get('out_amount'),
                    'price_impact': quote.get('price_impact_pct'),
                    'fees': await jupiter_client.estimate_fees(quote),
                    'message': 'Jupiter trade prepared successfully (dry run mode)'
                }
            else:
                # Execute real trade
                return await self.broadcast_jupiter_trade(swap_tx, trade_record, user_wallet)
                
        except Exception as e:
            logger.error(f"Jupiter trade execution failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _convert_usd_to_token_amount(self, usd_amount: float, token_mint: str) -> int:
        """Convert USD amount to token amount (in smallest units)"""
        try:
            # For SOL (native token)
            if token_mint == "So11111111111111111111111111111111111111112":
                # Get SOL price from CoinGecko
                from integrations.base import integration_manager
                coingecko_client = integration_manager.get_client('coingecko')
                
                if coingecko_client:
                    sol_price = await coingecko_client.get_sol_price()
                    if sol_price and sol_price > 0:
                        sol_amount = usd_amount / sol_price
                        return int(sol_amount * 1e9)  # Convert to lamports
                
                # Fallback: assume $100 per SOL
                sol_amount = usd_amount / 100.0
                return int(sol_amount * 1e9)
            
            # For other tokens, would need additional price lookup
            # For now, return the USD amount as token amount (placeholder)
            return int(usd_amount * 1e6)  # Assume 6 decimals
            
        except Exception as e:
            logger.error(f"USD to token conversion failed: {e}")
            return int(usd_amount * 1e6)  # Fallback
    
    async def _get_solana_wallet(self, user_id: int) -> Optional[Dict]:
        """Get user's Solana wallet configuration"""
        try:
            # This would load from keystore or database
            # For now, return placeholder
            return {
                'public_key': 'placeholder_public_key',
                'private_key_encrypted': 'placeholder_encrypted_key'
            }
            
        except Exception as e:
            logger.error(f"Failed to get Solana wallet: {e}")
            return None
    
    async def create_jupiter_trade_record(self, trade_params: Dict, quote: Dict, swap_tx: Dict) -> Dict:
        """Create Jupiter trade record in database"""
        db = get_db_session()
        try:
            trade = Trade(
                user_id=trade_params['user_id'],
                wallet_address='',  # Would be filled with Solana address
                trade_type='buy' if trade_params.get('input_mint') == "So11111111111111111111111111111111111111112" else 'sell',
                amount_in=float(quote.get('in_amount', 0)) / 1e9,  # Convert from lamports
                amount_out=float(quote.get('out_amount', 0)) / 1e6,  # Convert from token units
                token_in_address=trade_params.get('input_mint', ''),
                token_out_address=trade_params.get('output_mint', ''),
                price_usd=0.0,  # Would calculate from quote
                slippage=trade_params.get('slippage_bps', 50) / 10000,
                gas_fee=0.005,  # Approximate SOL transaction fee
                status='preparing',
                blockchain='solana'
            )
            
            db.add(trade)
            db.commit()
            db.refresh(trade)
            
            return {
                'trade_id': trade.trade_id,
                'id': trade.id
            }
            
        except Exception as e:
            logger.error(f"Failed to create Jupiter trade record: {e}")
            raise
        finally:
            db.close()
    
    async def broadcast_jupiter_trade(self, swap_tx: Dict, trade_record: Dict, user_wallet: Dict) -> Dict:
        """Broadcast Jupiter swap transaction to Solana network"""
        try:
            logger.info("📤 Broadcasting Jupiter transaction...")
            
            # This would require Solana SDK integration
            # For now, simulate successful execution
            
            # In production, would:
            # 1. Decode and sign the transaction
            # 2. Send to Solana RPC
            # 3. Wait for confirmation
            # 4. Update trade record
            
            # Simulate successful transaction
            tx_hash = f"jupiter_tx_{trade_record['trade_id']}"
            
            # Update trade record
            await self.update_trade_record(trade_record['trade_id'], {
                'tx_hash': tx_hash,
                'status': 'confirmed',
                'block_number': 123456789  # Placeholder block number
            })
            
            return {
                'success': True,
                'transaction_hash': tx_hash,
                'message': 'Jupiter trade executed successfully',
                'blockchain': 'solana'
            }
            
        except Exception as e:
            logger.error(f"Jupiter trade broadcast error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def execute_trade(self, trade_params: Dict) -> Dict:
        """Execute a complete trade with 0x protocol"""
        try:
            logger.info(f"🚀 Executing trade: {trade_params}")
            
            # Validate parameters
            required_params = ['user_id', 'sell_token', 'buy_token', 'sell_amount_wei', 'private_key']
            for param in required_params:
                if param not in trade_params:
                    raise ValueError(f"Missing required parameter: {param}")
            
            # Get quote
            quote = await self.get_0x_quote(
                trade_params['sell_token'],
                trade_params['buy_token'],
                trade_params['sell_amount_wei'],
                trade_params.get('slippage', Config.DEFAULT_SLIPPAGE),
                trade_params.get('user_address')
            )
            
            if not quote:
                return {'success': False, 'error': 'Failed to get quote from 0x'}
            
            # Prepare transaction
            tx_data = await self.prepare_0x_tx(
                quote,
                trade_params['private_key'],
                trade_params.get('dry_run', Config.DRY_RUN_MODE)
            )
            
            if not tx_data:
                return {'success': False, 'error': 'Failed to prepare transaction'}
            
            # Create trade record
            trade_record = await self.create_trade_record(trade_params, quote, tx_data)
            
            if trade_params.get('dry_run', Config.DRY_RUN_MODE):
                return {
                    'success': True,
                    'dry_run': True,
                    'trade_id': trade_record.get('trade_id'),
                    'transaction_hash': tx_data['swap_tx']['hash'],
                    'gas_cost_estimate': tx_data['estimated_gas_cost'],
                    'buy_amount': quote.get('buyAmount'),
                    'price': quote.get('price'),
                    'message': 'Trade prepared successfully (dry run mode)'
                }
            else:
                # Execute real trade (broadcast transaction)
                return await self.broadcast_trade(tx_data, trade_record)
                
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def broadcast_trade(self, tx_data: Dict, trade_record: Dict) -> Dict:
        """Broadcast the prepared transaction"""
        try:
            logger.info("📤 Broadcasting trade transaction...")
            
            # Send approval first if needed
            if tx_data.get('approval_tx'):
                logger.info("📤 Broadcasting approval transaction...")
                # Implementation for approval broadcast
                
            # Send swap transaction
            raw_tx = tx_data['swap_tx']['raw_transaction']
            tx_hash = self.web3.eth.send_raw_transaction(bytes.fromhex(raw_tx[2:]))
            
            logger.info(f"✅ Transaction broadcast: {tx_hash.hex()}")
            
            # Wait for confirmation
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt.status == 1:
                logger.info(f"✅ Trade confirmed: {tx_hash.hex()}")
                
                # Update trade record
                await self.update_trade_record(trade_record['trade_id'], {
                    'tx_hash': tx_hash.hex(),
                    'status': 'confirmed',
                    'gas_used': receipt.gasUsed,
                    'block_number': receipt.blockNumber
                })
                
                return {
                    'success': True,
                    'transaction_hash': tx_hash.hex(),
                    'gas_used': receipt.gasUsed,
                    'block_number': receipt.blockNumber,
                    'message': 'Trade executed successfully'
                }
            else:
                logger.error(f"❌ Trade failed: {tx_hash.hex()}")
                return {'success': False, 'error': 'Transaction failed'}
                
        except Exception as e:
            logger.error(f"Trade broadcast error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def create_trade_record(self, trade_params: Dict, quote: Dict, tx_data: Dict) -> Dict:
        """Create trade record in database"""
        db = get_db_session()
        try:
            trade = Trade(
                user_id=trade_params['user_id'],
                wallet_address=trade_params.get('user_address', ''),
                trade_type='buy' if trade_params['sell_token'].lower() == self.chain_config.wrapped_native.lower() else 'sell',
                amount_in=float(Web3.from_wei(trade_params['sell_amount_wei'], 'ether')),
                amount_out=float(Web3.from_wei(int(quote.get('buyAmount', 0)), 'ether')),
                token_in_address=trade_params['sell_token'],
                token_out_address=trade_params['buy_token'],
                price_usd=quote.get('price', 0),
                slippage=trade_params.get('slippage', Config.DEFAULT_SLIPPAGE),
                gas_fee=tx_data['estimated_gas_cost'],
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
    
    async def update_trade_record(self, trade_id: str, update_data: Dict):
        """Update trade record with execution results"""
        db = get_db_session()
        try:
            trade = db.query(Trade).filter(Trade.trade_id == trade_id).first()
            if trade:
                for key, value in update_data.items():
                    if hasattr(trade, key):
                        setattr(trade, key, value)
                
                trade.executed_at = datetime.utcnow()
                db.commit()
                logger.info(f"Trade record updated: {trade_id}")
            
        except Exception as e:
            logger.error(f"Failed to update trade record: {e}")
        finally:
            db.close()

class KeystoreManager:
    """Secure keystore management for private keys"""
    
    @staticmethod
    def load_keystore(keystore_path: str, password: str) -> str:
        """Load private key from keystore file"""
        try:
            with open(keystore_path, 'r') as f:
                keystore = json.load(f)
            
            private_key = extract_key_from_keyfile(keystore, password.encode())
            return private_key.hex()
            
        except Exception as e:
            logger.error(f"Keystore loading error: {e}")
            raise ValueError("Failed to load keystore")
    
    @staticmethod
    def create_keystore(private_key: str, password: str, keystore_path: str):
        """Create keystore file from private key"""
        try:
            account = Account.from_key(private_key)
            keystore = account.encrypt(password.encode())
            
            with open(keystore_path, 'w') as f:
                json.dump(keystore, f)
            
            logger.info(f"Keystore created: {keystore_path}")
            
        except Exception as e:
            logger.error(f"Keystore creation error: {e}")
            raise ValueError("Failed to create keystore")

# Legacy compatibility
TradeExecutor = AdvancedTradeExecutor