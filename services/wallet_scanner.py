"""
Advanced Wallet Scanner Service - Continuous monitoring of top wallets
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
from enum import Enum

from integrations.base import integration_manager
from core.trading_engine import trading_engine, TradeSignal
from db import get_db_session, WalletWatch, AlertConfig, Trade, User

logger = logging.getLogger(__name__)


class ChainType(Enum):
    ETHEREUM = "ethereum"
    BSC = "bsc"
    SOLANA = "solana"


@dataclass
class WalletTransaction:
    """Wallet transaction data"""
    wallet_address: str
    token_address: str
    token_symbol: str
    action: str  # 'buy' or 'sell'
    amount_usd: float
    token_amount: float
    transaction_hash: str
    block_number: int
    timestamp: datetime
    chain: ChainType
    gas_used: float = 0.0
    gas_price: float = 0.0


@dataclass
class TopWallet:
    """Top performing wallet data"""
    address: str
    total_pnl_usd: float
    win_rate: float
    total_trades: int
    best_trade_multiplier: float
    chains: List[str]
    last_active: datetime
    reputation_score: float


class WalletScanner:
    """Advanced wallet scanning service"""
    
    def __init__(self):
        self.is_running = False
        self.watched_wallets: Dict[str, TopWallet] = {}
        self.last_scan_blocks: Dict[ChainType, int] = {}
        self.scan_interval = 30  # seconds
        self.moonshot_threshold = 200.0  # 200x multiplier
        
        # Initialize with some high-performing wallets (you can customize these)
        self.initialize_top_wallets()
    
    def initialize_top_wallets(self):
        """Initialize with known high-performing wallets"""
        # These are example addresses - you can replace with actual top wallets
        top_wallets = [
            {
                'address': '0x8ba1f109551bD432803012645Hac136c22C501e3',
                'total_pnl_usd': 5000000.0,
                'win_rate': 85.5,
                'total_trades': 450,
                'best_trade_multiplier': 350.0,
                'chains': ['ethereum', 'bsc'],
                'reputation_score': 95.0
            },
            {
                'address': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984',
                'total_pnl_usd': 2500000.0,
                'win_rate': 78.2,
                'total_trades': 320,
                'best_trade_multiplier': 280.0,
                'chains': ['ethereum'],
                'reputation_score': 88.0
            },
            {
                'address': 'DUSTawucrTsGU8hcqRdHDCbuYhCPADMLM2VcCb8VnFnQ',
                'total_pnl_usd': 1800000.0,
                'win_rate': 82.1,
                'total_trades': 280,
                'best_trade_multiplier': 420.0,
                'chains': ['solana'],
                'reputation_score': 91.0
            }
        ]
        
        for wallet_data in top_wallets:
            wallet = TopWallet(
                address=wallet_data['address'],
                total_pnl_usd=wallet_data['total_pnl_usd'],
                win_rate=wallet_data['win_rate'],
                total_trades=wallet_data['total_trades'],
                best_trade_multiplier=wallet_data['best_trade_multiplier'],
                chains=wallet_data['chains'],
                last_active=datetime.utcnow(),
                reputation_score=wallet_data['reputation_score']
            )
            self.watched_wallets[wallet_data['address']] = wallet
    
    async def start_scanning(self):
        """Start continuous wallet scanning"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("🔍 Starting advanced wallet scanner...")
        
        # Load additional watched wallets from database
        await self.load_watched_wallets()
        
        # Start scanning tasks for each chain
        tasks = [
            asyncio.create_task(self.scan_chain(ChainType.ETHEREUM)),
            asyncio.create_task(self.scan_chain(ChainType.BSC)),
            asyncio.create_task(self.scan_chain(ChainType.SOLANA)),
        ]
        
        logger.info(f"🚀 Wallet scanner started - monitoring {len(self.watched_wallets)} wallets")
        
        # Wait for all scanning tasks
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_scanning(self):
        """Stop wallet scanning"""
        self.is_running = False
        logger.info("⏹️ Wallet scanner stopped")
    
    async def load_watched_wallets(self):
        """Load watched wallets from database"""
        db = get_db_session()
        try:
            watched = db.query(WalletWatch).filter(WalletWatch.is_active == True).all()
            
            for wallet_watch in watched:
                if wallet_watch.wallet_address not in self.watched_wallets:
                    # Create TopWallet from database data
                    top_wallet = TopWallet(
                        address=wallet_watch.wallet_address,
                        total_pnl_usd=wallet_watch.total_pnl or 0.0,
                        win_rate=wallet_watch.win_rate or 0.0,
                        total_trades=wallet_watch.total_trades or 0,
                        best_trade_multiplier=wallet_watch.best_multiplier or 1.0,
                        chains=wallet_watch.chains.split(',') if wallet_watch.chains else ['ethereum'],
                        last_active=wallet_watch.last_active or datetime.utcnow(),
                        reputation_score=wallet_watch.reputation_score or 50.0
                    )
                    self.watched_wallets[wallet_watch.wallet_address] = top_wallet
            
            logger.info(f"📋 Loaded {len(watched)} watched wallets from database")
            
        finally:
            db.close()
    
    async def scan_chain(self, chain: ChainType):
        """Scan specific chain for wallet activity"""
        while self.is_running:
            try:
                await self.scan_wallets_on_chain(chain)
                await asyncio.sleep(self.scan_interval)
            except Exception as e:
                logger.error(f"Error scanning {chain.value}: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def scan_wallets_on_chain(self, chain: ChainType):
        """Scan all watched wallets on a specific chain"""
        try:
            if chain == ChainType.SOLANA:
                await self.scan_solana_wallets()
            else:
                await self.scan_evm_wallets(chain)
                
        except Exception as e:
            logger.error(f"Failed to scan {chain.value} wallets: {e}")
    
    async def scan_evm_wallets(self, chain: ChainType):
        """Scan EVM chain wallets (Ethereum/BSC)"""
        try:
            covalent_client = integration_manager.get_client('covalent')
            if not covalent_client:
                return
            
            chain_id = 1 if chain == ChainType.ETHEREUM else 56
            
            for wallet_address, wallet_data in self.watched_wallets.items():
                # Skip Solana addresses
                if not wallet_address.startswith('0x'):
                    continue
                
                # Skip if chain not supported by this wallet
                if chain.value not in wallet_data.chains:
                    continue
                
                try:
                    # Get recent transactions
                    transactions = await covalent_client.get_transactions(
                        chain_id, 
                        wallet_address, 
                        page_size=50
                    )
                    
                    # Process transactions for trading signals
                    for tx in transactions:
                        await self.process_transaction(tx, wallet_address, chain)
                        
                except Exception as e:
                    logger.error(f"Error scanning wallet {wallet_address[:8]}... on {chain.value}: {e}")
                    continue
                
                # Small delay between wallets to avoid rate limits
                await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"EVM wallet scanning error: {e}")
    
    async def scan_solana_wallets(self):
        """Scan Solana wallets"""
        try:
            # For Solana, we'd need Solana RPC integration
            # For now, simulate with placeholder logic
            
            for wallet_address, wallet_data in self.watched_wallets.items():
                # Skip non-Solana addresses
                if wallet_address.startswith('0x'):
                    continue
                
                # Skip if Solana not supported
                if 'solana' not in wallet_data.chains:
                    continue
                
                # Placeholder - would implement actual Solana scanning
                # This would use Solana RPC to get recent transactions
                pass
                
        except Exception as e:
            logger.error(f"Solana wallet scanning error: {e}")
    
    async def process_transaction(self, tx: Dict, wallet_address: str, chain: ChainType):
        """Process a transaction for trading signals"""
        try:
            # Skip if transaction is too old
            tx_time = datetime.fromisoformat(tx.get('block_signed_at', '').replace('Z', '+00:00'))
            if datetime.utcnow() - tx_time.replace(tzinfo=None) > timedelta(hours=1):
                return
            
            # Check if this is a token trade
            if not self.is_token_trade(tx):
                return
            
            # Extract trading information
            trade_info = await self.extract_trade_info(tx, chain)
            if not trade_info:
                return
            
            # Create trading signal
            signal = TradeSignal(
                source_wallet=wallet_address,
                token_address=trade_info['token_address'],
                action=trade_info['action'],
                amount=trade_info['amount_usd'],
                price_usd=trade_info['price_usd'],
                transaction_hash=tx.get('tx_hash', ''),
                blockchain=chain.value,
                timestamp=tx_time.replace(tzinfo=None),
                confidence=self.calculate_signal_confidence(wallet_address, trade_info)
            )
            
            # Send alert and process signal
            await self.send_trading_alert(signal)
            await self.process_trading_signal(signal)
            
        except Exception as e:
            logger.error(f"Error processing transaction: {e}")
    
    def is_token_trade(self, tx: Dict) -> bool:
        """Check if transaction is a token trade"""
        # Check for DEX interactions
        to_address = tx.get('to_address', '').lower()
        
        # Known DEX router addresses
        dex_routers = {
            '0x7a250d5630b4cf539739df2c5dacb4c659f2488d',  # Uniswap V2
            '0xe592427a0aece92de3edee1f18e0157c05861564',  # Uniswap V3
            '0x10ed43c718714eb63d5aa57b78b54704e256024e',  # PancakeSwap
            '0x1b02da8cb0d097eb8d57a175b88c7d8b47997506',  # SushiSwap
        }
        
        return to_address in dex_routers
    
    async def extract_trade_info(self, tx: Dict, chain: ChainType) -> Optional[Dict]:
        """Extract trading information from transaction"""
        try:
            # This would parse the transaction logs to extract:
            # - Token being traded
            # - Buy/sell action
            # - Amount in USD
            # - Token price
            
            # Placeholder implementation
            return {
                'token_address': '0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b',
                'action': 'buy',  # or 'sell'
                'amount_usd': float(tx.get('value', 0)) / 1e18 * 2000,  # Estimate
                'price_usd': 0.001,  # Would calculate actual price
                'token_amount': 1000.0
            }
            
        except Exception as e:
            logger.error(f"Error extracting trade info: {e}")
            return None
    
    def calculate_signal_confidence(self, wallet_address: str, trade_info: Dict) -> float:
        """Calculate confidence score for trading signal"""
        wallet_data = self.watched_wallets.get(wallet_address)
        if not wallet_data:
            return 0.5
        
        # Base confidence on wallet performance
        confidence = wallet_data.win_rate / 100.0
        
        # Adjust for trade size
        if trade_info['amount_usd'] > 10000:  # Large trades get higher confidence
            confidence += 0.1
        elif trade_info['amount_usd'] < 1000:  # Small trades get lower confidence
            confidence -= 0.1
        
        # Adjust for wallet reputation
        confidence += (wallet_data.reputation_score - 50) / 100.0
        
        return max(0.1, min(1.0, confidence))
    
    async def send_trading_alert(self, signal: TradeSignal):
        """Send trading alert to all users"""
        try:
            # Get all users with alerts enabled
            db = get_db_session()
            try:
                users = db.query(User).all()
                
                for user in users:
                    # Check user's alert configuration
                    alert_config = db.query(AlertConfig).filter(
                        AlertConfig.user_id == user.id
                    ).first()
                    
                    if self.should_send_alert(signal, alert_config):
                        await self.send_telegram_alert(user.telegram_id, signal)
                        
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error sending trading alert: {e}")
    
    def should_send_alert(self, signal: TradeSignal, alert_config) -> bool:
        """Check if alert should be sent based on user configuration"""
        if not alert_config:
            return True  # Default: send all alerts
        
        # Check minimum trade size
        if signal.amount < alert_config.min_trade_size_usd:
            return False
        
        # Check chain filter
        if alert_config.monitored_chains and signal.blockchain not in alert_config.monitored_chains.split(','):
            return False
        
        # Check if wallet is blacklisted
        if alert_config.blacklisted_wallets and signal.source_wallet in alert_config.blacklisted_wallets.split(','):
            return False
        
        return True
    
    async def send_telegram_alert(self, telegram_id: str, signal: TradeSignal):
        """Send enhanced Telegram alert to user"""
        try:
            from bot import send_message_to_user
            from utils.formatting import AddressFormatter
            
            # Get wallet name if available
            wallet_name = f"Wallet {signal.source_wallet[-6:]}"
            
            # Format the alert with enhanced formatting
            message, buttons = AddressFormatter.format_trading_alert(
                wallet_address=signal.source_wallet,
                wallet_name=wallet_name,
                action=signal.action,
                token_address=signal.token_address,
                token_symbol=f"Token {signal.token_address[-6:]}",
                amount_usd=signal.amount,
                chain=signal.blockchain,
                tx_hash=signal.transaction_hash,
                confidence=signal.confidence
            )
            
            # Add action recommendation
            recommendation = self.get_action_recommendation(signal)
            message += f"\n\n**💡 Recommendation:**\n{recommendation}"
            
            # Send message with buttons
            await send_message_to_user(telegram_id, message, reply_markup=buttons)
            
            logger.info(f"📊 Enhanced alert sent to user {telegram_id}")
            
        except Exception as e:
            logger.error(f"Error sending enhanced alert: {e}")
            # Fallback to simple message
            await self._send_simple_alert(telegram_id, signal)
    
    async def _send_simple_alert(self, telegram_id: str, signal: TradeSignal):
        """Send simple alert as fallback"""
        try:
            from bot import send_message_to_user
            
            action_emoji = "🟢" if signal.action == "buy" else "🔴"
            
            message = f"""
{action_emoji} **WALLET ALERT**

**Action:** {signal.action.upper()}
**Wallet:** `{signal.source_wallet[:8]}...{signal.source_wallet[-6:]}`
**Token:** `{signal.token_address[:8]}...{signal.token_address[-6:]}`
**Amount:** ${signal.amount:,.2f}
**Chain:** {signal.blockchain.upper()}
**Time:** {signal.timestamp.strftime('%H:%M:%S')}
            """
            
            await send_message_to_user(telegram_id, message)
            
        except Exception as e:
            logger.error(f"Error sending simple alert: {e}")
    
    def get_action_recommendation(self, signal: TradeSignal) -> str:
        """Get action recommendation based on signal"""
        if signal.action == "sell" and trading_engine.config['mirror_sell_enabled']:
            return "🔄 **Mirror-sell will execute automatically**"
        elif signal.action == "buy" and signal.confidence > 0.8:
            return "💡 **Consider following this buy** (use /buy command)"
        elif signal.action == "buy":
            return "📊 **Monitor for confirmation** before following"
        else:
            return "📈 **Track for pattern analysis**"
    
    async def process_trading_signal(self, signal: TradeSignal):
        """Process trading signal through trading engine"""
        try:
            # Get all users for signal processing
            db = get_db_session()
            try:
                users = db.query(User).all()
                
                for user in users:
                    # Process signal for each user
                    result = await trading_engine.process_trade_signal(signal, str(user.telegram_id))
                    
                    if result and result.get('success'):
                        logger.info(f"✅ Processed signal for user {user.telegram_id}: {result.get('action', 'unknown')}")
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error processing trading signal: {e}")
    
    async def get_moonshot_leaderboard(self) -> List[TopWallet]:
        """Get wallets with 200x+ multipliers"""
        moonshot_wallets = []
        
        for wallet in self.watched_wallets.values():
            if wallet.best_trade_multiplier >= self.moonshot_threshold:
                moonshot_wallets.append(wallet)
        
        # Sort by best multiplier descending
        moonshot_wallets.sort(key=lambda w: w.best_trade_multiplier, reverse=True)
        
        return moonshot_wallets[:20]  # Top 20
    
    async def add_wallet_to_watchlist(self, wallet_address: str, user_id: int, 
                                    chains: List[str] = None) -> bool:
        """Add wallet to watchlist"""
        try:
            db = get_db_session()
            try:
                # Check if already exists
                existing = db.query(WalletWatch).filter(
                    WalletWatch.wallet_address == wallet_address,
                    WalletWatch.user_id == user_id
                ).first()
                
                if existing:
                    existing.is_active = True
                    existing.updated_at = datetime.utcnow()
                else:
                    wallet_watch = WalletWatch(
                        user_id=user_id,
                        wallet_address=wallet_address,
                        chains=','.join(chains or ['ethereum']),
                        is_active=True,
                        added_at=datetime.utcnow()
                    )
                    db.add(wallet_watch)
                
                db.commit()
                
                # Add to active scanning
                if wallet_address not in self.watched_wallets:
                    self.watched_wallets[wallet_address] = TopWallet(
                        address=wallet_address,
                        total_pnl_usd=0.0,
                        win_rate=0.0,
                        total_trades=0,
                        best_trade_multiplier=1.0,
                        chains=chains or ['ethereum'],
                        last_active=datetime.utcnow(),
                        reputation_score=50.0
                    )
                
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error adding wallet to watchlist: {e}")
            return False
    
    async def manual_scan(self) -> Dict[str, Any]:
        """Perform manual scan and return results"""
        try:
            logger.info("🔄 Performing manual wallet scan...")
            
            scan_results = {
                'scanned_wallets': len(self.watched_wallets),
                'new_transactions': 0,
                'alerts_sent': 0,
                'chains_scanned': [],
                'scan_time': datetime.utcnow()
            }
            
            # Force scan all chains
            for chain in [ChainType.ETHEREUM, ChainType.BSC, ChainType.SOLANA]:
                await self.scan_wallets_on_chain(chain)
                scan_results['chains_scanned'].append(chain.value)
            
            logger.info(f"✅ Manual scan completed: {scan_results}")
            return scan_results
            
        except Exception as e:
            logger.error(f"Manual scan error: {e}")
            return {'error': str(e)}


# Global wallet scanner instance
wallet_scanner = WalletScanner()