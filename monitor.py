import asyncio
import json
import logging
import websockets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from web3 import Web3
from config import Config
from db import get_db_session, Token, Wallet, Transaction, MonitoringAlert
from utils.api_client import CovalentClient

logger = logging.getLogger(__name__)

class MempoolMonitor:
    """Real-time mempool monitoring using Alchemy WebSockets"""
    
    def __init__(self, chain_id: int = 11155111):
        self.chain_id = chain_id
        self.is_running = False
        self.tracked_wallets: Set[str] = set()
        self.tracked_tokens: Set[str] = set()
        self.websocket = None
        
        # Configure WebSocket URL based on chain
        if chain_id == 11155111:  # Sepolia
            self.ws_url = Config.ALCHEMY_ETH_WS_URL
            self.rpc_url = Config.ETHEREUM_RPC_URL
        elif chain_id == 97:  # BSC Testnet
            self.ws_url = Config.ALCHEMY_BSC_WS_URL
            self.rpc_url = Config.BSC_RPC_URL
        else:
            raise ValueError(f"Unsupported chain ID: {chain_id}")
            
        self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        # Common router addresses for detecting swaps
        self.router_addresses = {
            Config.UNISWAP_V2_ROUTER.lower(),
            Config.PANCAKESWAP_ROUTER.lower(),
            Config.SUSHISWAP_ROUTER.lower()
        }
        
        # Common swap method signatures
        self.swap_methods = {
            '0x38ed1739',  # swapExactTokensForTokens
            '0x8803dbee',  # swapTokensForExactTokens
            '0x7ff36ab5',  # swapExactETHForTokens
            '0x18cbafe5',  # swapExactTokensForETH
            '0x791ac947',  # swapExactTokensForTokensSupportingFeeOnTransferTokens
            '0xb6f9de95'   # swapExactETHForTokensSupportingFeeOnTransferTokens
        }
    
    async def start_mempool_monitoring(self, tracked_wallets: List[str] = None, tracked_tokens: List[str] = None):
        """Start monitoring mempool for tracked wallets and tokens"""
        
        if tracked_wallets:
            self.tracked_wallets.update([addr.lower() for addr in tracked_wallets])
        if tracked_tokens:
            self.tracked_tokens.update([addr.lower() for addr in tracked_tokens])
        
        self.is_running = True
        logger.info(f"Starting mempool monitoring for {len(self.tracked_wallets)} wallets, {len(self.tracked_tokens)} tokens")
        
        # Start monitoring loop
        asyncio.create_task(self.mempool_monitoring_loop())
    
    async def stop_mempool_monitoring(self):
        """Stop mempool monitoring"""
        self.is_running = False
        if self.websocket:
            await self.websocket.close()
        logger.info("Mempool monitoring stopped")
    
    async def mempool_monitoring_loop(self):
        """Main mempool monitoring loop with WebSocket connection"""
        while self.is_running:
            try:
                await self.connect_and_monitor()
            except Exception as e:
                logger.error(f"Mempool monitoring error: {e}")
                await asyncio.sleep(30)  # Wait before reconnecting
    
    async def connect_and_monitor(self):
        """Connect to Alchemy WebSocket and monitor pending transactions"""
        try:
            logger.info(f"Connecting to mempool WebSocket: {self.ws_url[:50]}...")
            
            async with websockets.connect(self.ws_url) as websocket:
                self.websocket = websocket
                
                # Subscribe to pending transactions
                subscription = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_subscribe",
                    "params": ["newPendingTransactions", True]  # Include transaction details
                }
                
                await websocket.send(json.dumps(subscription))
                response = await websocket.recv()
                logger.info(f"Subscription response: {response}")
                
                # Monitor incoming messages
                while self.is_running:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30)
                        await self.process_mempool_message(message)
                        
                    except asyncio.TimeoutError:
                        # Send ping to keep connection alive
                        ping = {"jsonrpc": "2.0", "method": "ping", "id": "ping"}
                        await websocket.send(json.dumps(ping))
                        continue
                        
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            raise
    
    async def process_mempool_message(self, message: str):
        """Process incoming mempool transaction"""
        try:
            data = json.loads(message)
            
            if 'params' not in data:
                return
            
            tx_data = data['params']['result']
            if not tx_data:
                return
            
            # Extract transaction details
            from_addr = tx_data.get('from', '').lower()
            to_addr = tx_data.get('to', '').lower()
            tx_hash = tx_data.get('hash', '')
            input_data = tx_data.get('input', '')
            value = int(tx_data.get('value', '0x0'), 16)
            
            # Check if this is a transaction we care about
            is_tracked_wallet = from_addr in self.tracked_wallets
            is_router_interaction = to_addr in self.router_addresses
            is_swap_method = input_data[:10] in self.swap_methods
            
            if is_tracked_wallet and is_router_interaction and is_swap_method:
                logger.info(f"🚨 MEMPOOL ALERT: Tracked wallet {from_addr[:8]}... making swap")
                await self.process_tracked_wallet_swap(tx_data)
            
            elif is_router_interaction and is_swap_method and len(input_data) > 200:
                # Check if this involves any tracked tokens
                await self.check_token_involvement(tx_data)
                
        except Exception as e:
            logger.error(f"Error processing mempool message: {e}")
    
    async def process_tracked_wallet_swap(self, tx_data: Dict):
        """Process swap transaction from tracked wallet"""
        try:
            from_addr = tx_data.get('from', '').lower()
            tx_hash = tx_data.get('hash', '')
            input_data = tx_data.get('input', '')
            
            # Decode swap parameters
            swap_details = await self.decode_swap_transaction(tx_data)
            
            if swap_details:
                # Get token information
                token_address = swap_details.get('token_out')
                if token_address:
                    # Try to get current USD price
                    usd_price = await self.get_token_usd_price(token_address)
                    
                    # Create early alert
                    await self.create_mempool_alert(
                        wallet_address=from_addr,
                        token_address=token_address,
                        transaction_hash=tx_hash,
                        swap_details=swap_details,
                        usd_price=usd_price
                    )
                    
                    logger.info(f"📢 Mempool alert created for {from_addr[:8]}... buying {token_address[:8]}...")
            
        except Exception as e:
            logger.error(f"Error processing tracked wallet swap: {e}")
    
    async def check_token_involvement(self, tx_data: Dict):
        """Check if transaction involves any tracked tokens"""
        try:
            input_data = tx_data.get('input', '')
            
            # Look for token addresses in the transaction data
            for token_addr in self.tracked_tokens:
                if token_addr[2:].lower() in input_data.lower():  # Remove 0x prefix
                    logger.info(f"🎯 Tracked token {token_addr[:8]}... spotted in mempool")
                    await self.process_token_transaction(tx_data, token_addr)
                    break
                    
        except Exception as e:
            logger.error(f"Error checking token involvement: {e}")
    
    async def decode_swap_transaction(self, tx_data: Dict) -> Optional[Dict]:
        """Decode swap transaction to extract token details"""
        try:
            input_data = tx_data.get('input', '')
            method_sig = input_data[:10]
            
            # Basic decoding for common swap methods
            if method_sig == '0x7ff36ab5':  # swapExactETHForTokens
                # Extract parameters - this is simplified
                # In production, use proper ABI decoding
                return {
                    'method': 'swapExactETHForTokens',
                    'token_in': Config.get_wrapped_native_token(self.chain_id),
                    'token_out': 'unknown',  # Would need ABI decoding
                    'amount_in': int(tx_data.get('value', '0x0'), 16)
                }
            
            elif method_sig == '0x38ed1739':  # swapExactTokensForTokens
                return {
                    'method': 'swapExactTokensForTokens',
                    'token_in': 'unknown',  # Would need ABI decoding
                    'token_out': 'unknown',  # Would need ABI decoding
                    'amount_in': 0  # Would need ABI decoding
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error decoding swap transaction: {e}")
            return None
    
    async def get_token_usd_price(self, token_address: str) -> float:
        """Get current USD price for token"""
        try:
            # Try CoinGecko API first (placeholder implementation)
            # In production, implement proper price fetching
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting token USD price: {e}")
            return 0.0
    
    async def create_mempool_alert(self, wallet_address: str, token_address: str, 
                                 transaction_hash: str, swap_details: Dict, usd_price: float):
        """Create mempool alert in database"""
        db = get_db_session()
        try:
            # Find user associated with wallet
            wallet = db.query(Wallet).filter(Wallet.address == wallet_address).first()
            user_id = wallet.user_id if wallet else None
            
            alert = MonitoringAlert(
                user_id=user_id,
                alert_type='mempool_swap_detected',
                title='Mempool Swap Alert',
                message=f'Tracked wallet {wallet_address[:8]}... detected buying {token_address[:8]}... in mempool',
                token_address=token_address,
                wallet_address=wallet_address,
                trigger_value=usd_price
            )
            db.add(alert)
            db.commit()
            
            logger.info(f"Mempool alert created for wallet {wallet_address}")
            
        except Exception as e:
            logger.error(f"Error creating mempool alert: {e}")
        finally:
            db.close()

class EnhancedTokenMonitor:
    """Enhanced token monitoring with price alerts and trend detection"""
    
    def __init__(self):
        self.covalent_client = CovalentClient()
        self.monitoring_tokens = {}
        self.is_running = False
        self.price_history = {}  # Track price history for trend analysis
        
    async def start_monitoring(self, token_addresses: List[str], user_id: str, 
                             price_threshold: float = 0.05):
        """Start monitoring specified tokens with custom price threshold"""
        self.is_running = True
        logger.info(f"Starting enhanced token monitoring for {len(token_addresses)} tokens")
        
        for address in token_addresses:
            self.monitoring_tokens[address] = {
                'user_id': user_id,
                'last_price': None,
                'last_check': datetime.utcnow(),
                'alerts_sent': 0,
                'price_threshold': price_threshold,
                'trend': 'neutral'
            }
            
            # Initialize price history
            self.price_history[address] = []
        
        # Start monitoring loop
        asyncio.create_task(self.enhanced_monitoring_loop())
        
    async def stop_monitoring(self):
        """Stop token monitoring"""
        self.is_running = False
        self.monitoring_tokens.clear()
        self.price_history.clear()
        logger.info("Enhanced token monitoring stopped")
        
    async def enhanced_monitoring_loop(self):
        """Enhanced monitoring loop with trend analysis"""
        while self.is_running:
            try:
                await self.check_all_tokens_enhanced()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Enhanced monitoring loop error: {e}")
                await asyncio.sleep(60)  # Wait longer on error
                
    async def check_all_tokens_enhanced(self):
        """Check all monitored tokens with enhanced analysis"""
        for token_address, data in self.monitoring_tokens.items():
            try:
                await self.check_token_enhanced(token_address, data)
            except Exception as e:
                logger.error(f"Error checking token {token_address}: {e}")
                
    async def check_token_enhanced(self, token_address: str, monitor_data: Dict):
        """Enhanced token checking with trend analysis"""
        try:
            # Get current token data
            token_data = await self.covalent_client.get_token_data(token_address)
            
            if not token_data:
                return
                
            current_price = token_data.get('price_usd', 0)
            last_price = monitor_data['last_price']
            threshold = monitor_data['price_threshold']
            
            # Update price history
            self.price_history[token_address].append({
                'price': current_price,
                'timestamp': datetime.utcnow()
            })
            
            # Keep only last 100 price points
            if len(self.price_history[token_address]) > 100:
                self.price_history[token_address] = self.price_history[token_address][-100:]
            
            # Update database
            await self.update_token_in_db(token_address, token_data)
            
            # Analyze trends
            trend = self.analyze_price_trend(token_address)
            monitor_data['trend'] = trend
            
            # Check for significant price changes
            if last_price and current_price > 0:
                price_change = ((current_price - last_price) / last_price) * 100
                
                # Alert on significant changes based on custom threshold
                if abs(price_change) >= threshold * 100:
                    alert_type = 'pump' if price_change > 0 else 'dump'
                    await self.create_enhanced_price_alert(
                        token_address, 
                        monitor_data['user_id'],
                        price_change,
                        current_price,
                        last_price,
                        trend,
                        alert_type
                    )
            
            # Update monitoring data
            monitor_data['last_price'] = current_price
            monitor_data['last_check'] = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Enhanced token check error for {token_address}: {e}")
    
    def analyze_price_trend(self, token_address: str) -> str:
        """Analyze price trend from recent history"""
        try:
            history = self.price_history.get(token_address, [])
            if len(history) < 5:
                return 'neutral'
            
            # Get last 5 prices
            recent_prices = [point['price'] for point in history[-5:]]
            
            # Calculate trend
            increases = 0
            decreases = 0
            
            for i in range(1, len(recent_prices)):
                if recent_prices[i] > recent_prices[i-1]:
                    increases += 1
                elif recent_prices[i] < recent_prices[i-1]:
                    decreases += 1
            
            if increases >= 3:
                return 'bullish'
            elif decreases >= 3:
                return 'bearish'
            else:
                return 'neutral'
                
        except Exception as e:
            logger.error(f"Trend analysis error: {e}")
            return 'neutral'
    
    async def update_token_in_db(self, token_address: str, token_data: Dict):
        """Update token data in database with trend information"""
        db = get_db_session()
        try:
            token = db.query(Token).filter(Token.address == token_address).first()
            if not token:
                token = Token(address=token_address)
                db.add(token)
            
            # Update token data
            token.name = token_data.get('name')
            token.symbol = token_data.get('symbol')
            token.decimals = token_data.get('decimals')
            token.price_usd = token_data.get('price_usd')
            token.market_cap = token_data.get('market_cap')
            token.liquidity_usd = token_data.get('liquidity_usd')
            token.volume_24h = token_data.get('volume_24h')
            token.last_analyzed = datetime.utcnow()
            token.updated_at = datetime.utcnow()
            
            db.commit()
        finally:
            db.close()
    
    async def create_enhanced_price_alert(self, token_address: str, user_id: str, 
                                        price_change: float, current_price: float, 
                                        last_price: float, trend: str, alert_type: str):
        """Create enhanced price change alert with trend information"""
        db = get_db_session()
        try:
            # Get token info
            token = db.query(Token).filter(Token.address == token_address).first()
            token_symbol = token.symbol if token else token_address[:8]
            
            # Create enhanced alert message
            trend_emoji = {'bullish': '📈', 'bearish': '📉', 'neutral': '➡️'}
            alert_emoji = {'pump': '🚀', 'dump': '📉'}
            
            message = (f"{alert_emoji.get(alert_type, '⚠️')} {token_symbol} {alert_type.upper()}\n"
                      f"Price: ${last_price:.6f} → ${current_price:.6f}\n"
                      f"Change: {price_change:+.2f}%\n"
                      f"Trend: {trend_emoji.get(trend, '➡️')} {trend.upper()}")
            
            alert = MonitoringAlert(
                user_id=int(user_id),
                alert_type=f'price_{alert_type}',
                title=f'{token_symbol} Price {alert_type.capitalize()}',
                message=message,
                token_address=token_address,
                trigger_value=price_change
            )
            db.add(alert)
            db.commit()
            
            logger.info(f"Enhanced price alert created for {token_symbol}: {price_change:.2f}% ({trend})")
            
        finally:
            db.close()

class WalletMonitor:
    """Enhanced wallet monitoring with transaction categorization"""
    
    def __init__(self):
        self.covalent_client = CovalentClient()
        self.monitoring_wallets = {}
        self.is_running = False
        
    async def start_monitoring(self, wallet_addresses: List[str], user_id: str):
        """Start monitoring specified wallets"""
        self.is_running = True
        logger.info(f"Starting wallet monitoring for {len(wallet_addresses)} wallets")
        
        for address in wallet_addresses:
            self.monitoring_wallets[address] = {
                'user_id': user_id,
                'last_block_checked': 0,
                'last_check': datetime.utcnow(),
                'transaction_count': 0
            }
        
        # Start monitoring loop
        asyncio.create_task(self.wallet_monitoring_loop())
        
    async def stop_monitoring(self):
        """Stop wallet monitoring"""
        self.is_running = False
        self.monitoring_wallets.clear()
        logger.info("Wallet monitoring stopped")
        
    async def wallet_monitoring_loop(self):
        """Enhanced wallet monitoring loop"""
        while self.is_running:
            try:
                await self.check_all_wallets()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Wallet monitoring loop error: {e}")
                await asyncio.sleep(120)  # Wait longer on error
                
    async def check_all_wallets(self):
        """Check all monitored wallets for new transactions"""
        for wallet_address, data in self.monitoring_wallets.items():
            try:
                await self.check_wallet_enhanced(wallet_address, data)
            except Exception as e:
                logger.error(f"Error checking wallet {wallet_address}: {e}")
                
    async def check_wallet_enhanced(self, wallet_address: str, monitor_data: Dict):
        """Enhanced wallet checking with transaction categorization"""
        try:
            # Get recent transactions
            transactions = await self.covalent_client.get_wallet_transactions(
                wallet_address, 
                from_block=monitor_data['last_block_checked']
            )
            
            if not transactions:
                return
                
            # Process new transactions with categorization
            new_transactions = 0
            for tx in transactions:
                if await self.process_transaction_enhanced(wallet_address, tx, monitor_data['user_id']):
                    new_transactions += 1
                    
            if new_transactions > 0:
                await self.create_wallet_activity_alert(
                    wallet_address,
                    monitor_data['user_id'], 
                    new_transactions,
                    transactions[:3]  # Show first 3 transactions
                )
                
            # Update monitoring data
            if transactions:
                monitor_data['last_block_checked'] = max(tx.get('block_number', 0) for tx in transactions)
                monitor_data['transaction_count'] += new_transactions
            monitor_data['last_check'] = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Enhanced wallet check error for {wallet_address}: {e}")
    
    async def process_transaction_enhanced(self, wallet_address: str, tx_data: Dict, user_id: str) -> bool:
        """Process transaction with enhanced categorization"""
        db = get_db_session()
        try:
            # Check if transaction already exists
            existing_tx = db.query(Transaction).filter(
                Transaction.tx_hash == tx_data.get('tx_hash')
            ).first()
            
            if existing_tx:
                return False
                
            # Get wallet from database
            wallet = db.query(Wallet).filter(Wallet.address == wallet_address).first()
            if not wallet:
                return False
            
            # Enhanced transaction categorization
            tx_type = self.categorize_transaction(tx_data, wallet_address)
            
            # Create transaction record
            transaction = Transaction(
                wallet_id=wallet.id,
                tx_hash=tx_data.get('tx_hash'),
                from_address=tx_data.get('from_address'),
                to_address=tx_data.get('to_address'),
                value=float(tx_data.get('value', 0)),
                token_address=tx_data.get('token_address'),
                token_symbol=tx_data.get('token_symbol'),
                gas_used=tx_data.get('gas_used'),
                gas_price=float(tx_data.get('gas_price', 0)),
                block_number=tx_data.get('block_number'),
                timestamp=datetime.fromisoformat(tx_data.get('timestamp', datetime.utcnow().isoformat())),
                transaction_type=tx_type
            )
            
            db.add(transaction)
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error processing enhanced transaction: {e}")
            return False
        finally:
            db.close()
    
    def categorize_transaction(self, tx_data: Dict, wallet_address: str) -> str:
        """Enhanced transaction categorization"""
        from_addr = tx_data.get('from_address', '').lower()
        to_addr = tx_data.get('to_address', '').lower()
        wallet_addr = wallet_address.lower()
        input_data = tx_data.get('input', '')
        
        # Check for DEX interaction
        if to_addr in {Config.UNISWAP_V2_ROUTER.lower(), Config.PANCAKESWAP_ROUTER.lower()}:
            if input_data[:10] in {'0x7ff36ab5', '0x38ed1739'}:  # Swap methods
                return 'dex_swap'
            elif input_data[:10] == '0xe8e33700':  # Add liquidity
                return 'add_liquidity'
            elif input_data[:10] == '0xbaa2abde':  # Remove liquidity
                return 'remove_liquidity'
        
        # Standard categorization
        if from_addr == wallet_addr:
            return 'send'
        elif to_addr == wallet_addr:
            return 'receive'
        else:
            return 'interaction'
    
    async def create_wallet_activity_alert(self, wallet_address: str, user_id: str, 
                                         tx_count: int, sample_transactions: List[Dict]):
        """Create enhanced wallet activity alert"""
        db = get_db_session()
        try:
            # Analyze transaction types
            tx_types = [self.categorize_transaction(tx, wallet_address) for tx in sample_transactions]
            type_summary = {}
            for tx_type in tx_types:
                type_summary[tx_type] = type_summary.get(tx_type, 0) + 1
            
            # Create detailed message
            summary = ", ".join([f"{count} {tx_type}" for tx_type, count in type_summary.items()])
            
            alert = MonitoringAlert(
                user_id=int(user_id),
                alert_type='wallet_activity',
                title='Wallet Activity Detected',
                message=f'{tx_count} new transaction(s) in wallet {wallet_address[:8]}...{wallet_address[-8:]}\nActivity: {summary}',
                wallet_address=wallet_address,
                trigger_value=tx_count
            )
            db.add(alert)
            db.commit()
            
            logger.info(f"Wallet activity alert created for {wallet_address}: {tx_count} transactions")
            
        finally:
            db.close()

class EnhancedMonitoringManager:
    """Centralized enhanced monitoring management"""
    
    def __init__(self):
        self.token_monitor = EnhancedTokenMonitor()
        self.wallet_monitor = WalletMonitor()
        self.mempool_monitor = MempoolMonitor()
        
    async def start_comprehensive_monitoring(self, user_id: str, config: Dict):
        """Start comprehensive monitoring based on user configuration"""
        
        # Start token monitoring
        if config.get('tokens'):
            await self.token_monitor.start_monitoring(
                config['tokens'], 
                user_id, 
                config.get('price_threshold', 0.05)
            )
        
        # Start wallet monitoring
        if config.get('wallets'):
            await self.wallet_monitor.start_monitoring(config['wallets'], user_id)
        
        # Start mempool monitoring
        if config.get('mempool_tracking'):
            await self.mempool_monitor.start_mempool_monitoring(
                config.get('wallets'), 
                config.get('tokens')
            )
        
        logger.info(f"Comprehensive monitoring started for user {user_id}")
    
    async def stop_all_monitoring(self):
        """Stop all monitoring services"""
        await self.token_monitor.stop_monitoring()
        await self.wallet_monitor.stop_monitoring()
        await self.mempool_monitor.stop_mempool_monitoring()
        logger.info("All monitoring services stopped")
    
    async def get_monitoring_status(self) -> Dict:
        """Get comprehensive monitoring status"""
        return {
            'token_monitor_running': self.token_monitor.is_running,
            'wallet_monitor_running': self.wallet_monitor.is_running,
            'mempool_monitor_running': self.mempool_monitor.is_running,
            'monitored_tokens': len(self.token_monitor.monitoring_tokens),
            'monitored_wallets': len(self.wallet_monitor.monitoring_wallets),
            'tracked_wallets_mempool': len(self.mempool_monitor.tracked_wallets),
            'tracked_tokens_mempool': len(self.mempool_monitor.tracked_tokens)
        }

# Legacy compatibility
TokenMonitor = EnhancedTokenMonitor
MonitoringManager = EnhancedMonitoringManager