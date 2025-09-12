import asyncio
import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

from db.models import get_db_manager
from services.covalent import CovalentClient
from services.helius import HeliusClient
from services.go_plus import GoPlusClient
from utils.key_manager import get_key_manager
from utils.formatting import AddressFormatter

logger = logging.getLogger(__name__)

@dataclass
class TradeAlert:
    """Represents a trade alert from a watched wallet"""
    wallet_address: str
    wallet_label: str
    chain: str
    action: str  # "BUY" or "SELL"
    token_address: str
    token_name: str
    token_symbol: str
    amount_tokens: float
    amount_usd: float
    tx_hash: str
    timestamp: datetime
    trader_win_rate: float
    trader_roi: float
    trader_trades_30d: int
    risk_score: int
    is_safe: bool
    consensus_boost: bool = False

@dataclass
class ConsensusAlert:
    """Represents a consensus buy alert when multiple wallets buy the same token"""
    token_address: str
    token_name: str
    token_symbol: str
    wallet_count: int
    total_volume_usd: float
    timestamp: datetime
    wallets: List[str]

class WatchlistMonitor:
    """Real-time watchlist monitoring with instant trade alerts"""
    
    def __init__(self):
        self.db = get_db_manager()
        self.key_manager = get_key_manager()
        self.covalent_client = None
        self.helius_client = None
        self.goplus_client = None
        self.monitoring = False
        self.last_check_times: Dict[str, datetime] = {}
        self.consensus_cache: Dict[str, List[TradeAlert]] = {}
        self.alert_cache: Set[str] = set()  # Prevent duplicate alerts
        
    async def initialize(self):
        """Initialize API clients"""
        try:
            if self.key_manager.is_service_available('covalent'):
                self.covalent_client = CovalentClient()
            if self.key_manager.is_service_available('helius'):
                self.helius_client = HeliusClient()
            if self.key_manager.is_service_available('goplus'):
                self.goplus_client = GoPlusClient()
            logger.info("Watchlist monitor initialized")
        except Exception as e:
            logger.error(f"Failed to initialize watchlist monitor: {e}")
    
    async def start_monitoring(self):
        """Start real-time monitoring of watchlist addresses"""
        if self.monitoring:
            return
        
        self.monitoring = True
        logger.info("Starting watchlist monitoring...")
        
        # Start monitoring tasks
        asyncio.create_task(self._monitor_evm_chains())
        asyncio.create_task(self._monitor_solana())
        asyncio.create_task(self._consensus_detector())
    
    async def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        logger.info("Watchlist monitoring stopped")
    
    async def _monitor_evm_chains(self):
        """Monitor EVM chains (Ethereum, BSC) for trade activity"""
        while self.monitoring:
            try:
                # Get all watchlist entries
                watchlist = self.db.get_user_watchlist(user_id=None)
                
                for entry in watchlist:
                    if entry['chain'] in ['ethereum', 'bsc']:
                        await self._check_wallet_trades(entry)
                
                # Check every 30 seconds for EVM chains
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"EVM monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _monitor_solana(self):
        """Monitor Solana for trade activity"""
        while self.monitoring:
            try:
                # Get Solana watchlist entries
                watchlist = self.db.get_user_watchlist(user_id=None)
                solana_entries = [e for e in watchlist if e['chain'] == 'solana']
                
                for entry in solana_entries:
                    await self._check_solana_trades(entry)
                
                # Check every 15 seconds for Solana (faster)
                await asyncio.sleep(15)
            except Exception as e:
                logger.error(f"Solana monitoring error: {e}")
                await asyncio.sleep(30)
    
    async def _check_wallet_trades(self, entry: dict):
        """Check a specific wallet for new trades"""
        try:
            address = entry['address']
            chain = entry['chain']
            label = entry.get('label', address[:8])
            
            # Get last check time
            last_check = self.last_check_times.get(f"{chain}:{address}")
            if not last_check:
                last_check = datetime.now() - timedelta(hours=1)
                self.last_check_times[f"{chain}:{address}"] = last_check
            
            # Get recent transactions
            if self.covalent_client:
                txs = await self.covalent_client.get_wallet_transactions(
                    address, 
                    chain_id=self._get_chain_id(chain),
                    start_date=last_check.isoformat()
                )
                
                for tx in txs:
                    if self._is_trade_transaction(tx):
                        alert = await self._create_trade_alert(entry, tx, chain)
                        if alert and self._should_send_alert(alert):
                            await self._send_trade_alert(alert)
            
            # Update last check time
            self.last_check_times[f"{chain}:{address}"] = datetime.now()
            
        except Exception as e:
            logger.error(f"Error checking wallet {entry['address']}: {e}")
    
    async def _check_solana_trades(self, entry: dict):
        """Check Solana wallet for new trades"""
        try:
            address = entry['address']
            label = entry.get('label', address[:8])
            
            if self.helius_client:
                # Get recent transactions from Helius
                txs = await self.helius_client.get_recent_transactions(address)
                
                for tx in txs:
                    if self._is_solana_trade(tx):
                        alert = await self._create_solana_alert(entry, tx)
                        if alert and self._should_send_alert(alert):
                            await self._send_trade_alert(alert)
                            
        except Exception as e:
            logger.error(f"Error checking Solana wallet {entry['address']}: {e}")
    
    def _is_trade_transaction(self, tx: dict) -> bool:
        """Check if transaction is a trade (buy/sell)"""
        # Look for token transfer events or DEX interactions
        if 'log_events' in tx:
            for event in tx['log_events']:
                if event.get('decoded', {}).get('name') in ['Transfer', 'Swap']:
                    return True
        return False
    
    def _is_solana_trade(self, tx: dict) -> bool:
        """Check if Solana transaction is a trade"""
        # Look for Jupiter or Raydium swap instructions
        if 'instructions' in tx:
            for instruction in tx['instructions']:
                if 'programId' in instruction:
                    program_id = instruction['programId']
                    # Jupiter, Raydium, Orca program IDs
                    if program_id in [
                        'JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB',  # Jupiter
                        '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8',  # Raydium
                        '9W959DqEETiGZocYWCQPaJ6sBmUzgPx2p9sK1e7f4Yd'   # Orca
                    ]:
                        return True
        return False
    
    async def _create_trade_alert(self, entry: dict, tx: dict, chain: str) -> Optional[TradeAlert]:
        """Create a trade alert from transaction data"""
        try:
            # Extract trade information
            action = self._determine_trade_action(tx)
            token_info = self._extract_token_info(tx, chain)
            
            if not token_info:
                return None
            
            # Get trader metrics
            trader_metrics = await self._get_trader_metrics(entry['address'], chain)
            
            # Perform safety analysis
            risk_score, is_safe = await self._analyze_token_safety(
                token_info['address'], 
                chain
            )
            
            alert = TradeAlert(
                wallet_address=entry['address'],
                wallet_label=entry.get('label', entry['address'][:8]),
                chain=chain,
                action=action,
                token_address=token_info['address'],
                token_name=token_info['name'],
                token_symbol=token_info['symbol'],
                amount_tokens=token_info['amount'],
                amount_usd=token_info['usd_value'],
                tx_hash=tx['tx_hash'],
                timestamp=datetime.fromisoformat(tx['block_signed_at'].replace('Z', '+00:00')),
                trader_win_rate=trader_metrics['win_rate'],
                trader_roi=trader_metrics['roi'],
                trader_trades_30d=trader_metrics['trades_30d'],
                risk_score=risk_score,
                is_safe=is_safe
            )
            
            return alert
            
        except Exception as e:
            logger.error(f"Error creating trade alert: {e}")
            return None
    
    async def _create_solana_alert(self, entry: dict, tx: dict) -> Optional[TradeAlert]:
        """Create a Solana trade alert"""
        try:
            # Extract Solana trade information
            action = self._determine_solana_action(tx)
            token_info = self._extract_solana_token_info(tx)
            
            if not token_info:
                return None
            
            # Get trader metrics
            trader_metrics = await self._get_trader_metrics(entry['address'], 'solana')
            
            # Perform safety analysis
            risk_score, is_safe = await self._analyze_token_safety(
                token_info['address'], 
                'solana'
            )
            
            alert = TradeAlert(
                wallet_address=entry['address'],
                wallet_label=entry.get('label', entry['address'][:8]),
                chain='solana',
                action=action,
                token_address=token_info['address'],
                token_name=token_info['name'],
                token_symbol=token_info['symbol'],
                amount_tokens=token_info['amount'],
                amount_usd=token_info['usd_value'],
                tx_hash=tx['signature'],
                timestamp=datetime.fromtimestamp(tx['blockTime']),
                trader_win_rate=trader_metrics['win_rate'],
                trader_roi=trader_metrics['roi'],
                trader_trades_30d=trader_metrics['trades_30d'],
                risk_score=risk_score,
                is_safe=is_safe
            )
            
            return alert
            
        except Exception as e:
            logger.error(f"Error creating Solana alert: {e}")
            return None
    
    def _determine_trade_action(self, tx: dict) -> str:
        """Determine if transaction is BUY or SELL"""
        # Analyze token transfers to determine direction
        # This is a simplified implementation
        return "BUY"  # Placeholder
    
    def _determine_solana_action(self, tx: dict) -> str:
        """Determine Solana trade action"""
        return "BUY"  # Placeholder
    
    def _extract_token_info(self, tx: dict, chain: str) -> Optional[dict]:
        """Extract token information from transaction"""
        # This would parse the transaction logs to extract token details
        # For now, return mock data
        return {
            'address': '0x1234567890123456789012345678901234567890',
            'name': 'Mock Token',
            'symbol': 'MOCK',
            'amount': 1000.0,
            'usd_value': 500.0
        }
    
    def _extract_solana_token_info(self, tx: dict) -> Optional[dict]:
        """Extract Solana token information"""
        return {
            'address': 'So11111111111111111111111111111111111111112',  # SOL
            'name': 'Solana',
            'symbol': 'SOL',
            'amount': 10.0,
            'usd_value': 200.0
        }
    
    async def _get_trader_metrics(self, address: str, chain: str) -> dict:
        """Get trader performance metrics"""
        try:
            # This would query the database for trader performance
            return {
                'win_rate': 75.0,
                'roi': 150.0,
                'trades_30d': 25
            }
        except Exception as e:
            logger.error(f"Error getting trader metrics: {e}")
            return {'win_rate': 0.0, 'roi': 0.0, 'trades_30d': 0}
    
    async def _analyze_token_safety(self, token_address: str, chain: str) -> tuple[int, bool]:
        """Analyze token safety using GoPlus and other tools"""
        try:
            if self.goplus_client:
                # Perform honeypot simulation
                honeypot_result = await self.goplus_client.check_honeypot(token_address, chain)
                
                # Check liquidity
                liquidity_result = await self.goplus_client.check_liquidity(token_address, chain)
                
                # Calculate risk score
                risk_score = 0
                if honeypot_result.get('is_honeypot', False):
                    risk_score += 50
                if liquidity_result.get('liquidity_usd', 0) < 10000:
                    risk_score += 30
                
                is_safe = risk_score < 30
                return risk_score, is_safe
            
            return 50, False  # Default to risky if no analysis available
            
        except Exception as e:
            logger.error(f"Error analyzing token safety: {e}")
            return 50, False
    
    def _should_send_alert(self, alert: TradeAlert) -> bool:
        """Check if alert should be sent (avoid duplicates)"""
        alert_key = f"{alert.wallet_address}:{alert.tx_hash}"
        if alert_key in self.alert_cache:
            return False
        
        self.alert_cache.add(alert_key)
        return True
    
    async def _send_trade_alert(self, alert: TradeAlert):
        """Send trade alert to users"""
        try:
            # Format alert message
            message = self._format_alert_message(alert)
            
            # Get all users who have this wallet in their watchlist
            users = self.db.get_watchlist_users(alert.wallet_address, alert.chain)
            
            for user_id in users:
                # Send alert to user
                await self._send_alert_to_user(user_id, message, alert)
            
            # Store alert in database
            self.db.store_trade_alert(alert)
            
        except Exception as e:
            logger.error(f"Error sending trade alert: {e}")
    
    def _format_alert_message(self, alert: TradeAlert) -> str:
        """Format trade alert message"""
        safety_icon = "✅ SAFE" if alert.is_safe else "🚫 RISK"
        consensus_icon = "🚀" if alert.consensus_boost else ""
        
        message = f"""
{consensus_icon} **Trade Alert** {safety_icon}

**Wallet:** {alert.wallet_label} ({alert.wallet_address[:8]}...)
**Action:** {alert.action}
**Token:** {alert.token_name} ({alert.token_symbol})
**Amount:** {alert.amount_tokens:,.2f} {alert.token_symbol} (${alert.amount_usd:,.2f})
**Tx:** {AddressFormatter.format_transaction_hash(alert.tx_hash, alert.chain)}
**Time:** {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

**Trader Stats:**
• Win Rate: {alert.trader_win_rate:.1f}%
• ROI: {alert.trader_roi:.1f}x
• Trades (30d): {alert.trader_trades_30d}

**Risk Score:** {alert.risk_score}/100
"""
        return message
    
    async def _send_alert_to_user(self, user_id: str, message: str, alert: TradeAlert):
        """Send alert to specific user with inline buttons"""
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            # Actionable buttons: Analyze Token, Buy, Blacklist, Copy Contract
            keyboard = []
            if alert:
                keyboard.append([
                    InlineKeyboardButton("Analyze Token", callback_data=f"buy_analyze_{alert.token_address}_{alert.chain}"),
                    InlineKeyboardButton("Buy", callback_data=f"buy_quick_{alert.token_address}_50_{alert.chain}")
                ])
                keyboard.append([
                    InlineKeyboardButton("Blacklist Token", callback_data=f"blacklist_token_{alert.token_address}"),
                    InlineKeyboardButton("Copy Contract", callback_data=f"copy_address_{alert.token_address}")
                ])
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            # Integrate with bot to send message (replace with actual send logic)
            # For demo, just log
            logger.info(f"Sending alert to user {user_id}: {message}")
            # Example: await bot.send_message(user_id, message, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to send alert to user {user_id}: {e}")
    
    async def _consensus_detector(self):
        """Detect consensus buys (multiple wallets buying same token)"""
        while self.monitoring:
            try:
                # Check for consensus patterns
                await self._check_consensus_patterns()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Consensus detector error: {e}")
                await asyncio.sleep(120)
    
    async def _check_consensus_patterns(self):
        """Check for consensus buy patterns"""
        try:
            # Group recent alerts by token
            token_alerts = {}
            recent_alerts = self.db.get_recent_alerts(minutes=15)
            
            for alert in recent_alerts:
                if alert.action == "BUY":
                    key = f"{alert.chain}:{alert.token_address}"
                    if key not in token_alerts:
                        token_alerts[key] = []
                    token_alerts[key].append(alert)
            
            # Check for consensus (3+ wallets buying same token in 15min)
            for token_key, alerts in token_alerts.items():
                if len(alerts) >= 3:
                    await self._send_consensus_alert(alerts)
                    
        except Exception as e:
            logger.error(f"Error checking consensus patterns: {e}")
    
    async def _send_consensus_alert(self, alerts: List[TradeAlert]):
        """Send consensus buy alert"""
        try:
            token = alerts[0]
            total_volume = sum(alert.amount_usd for alert in alerts)
            
            consensus_alert = ConsensusAlert(
                token_address=token.token_address,
                token_name=token.token_name,
                token_symbol=token.token_symbol,
                wallet_count=len(alerts),
                total_volume_usd=total_volume,
                timestamp=datetime.now(),
                wallets=[alert.wallet_address for alert in alerts]
            )
            
            # Send consensus alert
            message = f"""
🚀 **CONSENSUS BUY ALERT** 🚀

**Token:** {consensus_alert.token_name} ({consensus_alert.token_symbol})
**Wallets:** {consensus_alert.wallet_count} traders
**Total Volume:** ${consensus_alert.total_volume_usd:,.2f}
**Time:** {consensus_alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

**Traders:**
{chr(10).join([f"• {alert.wallet_label} ({alert.trader_win_rate:.1f}% win rate)" for alert in alerts])}
"""
            
            # Send to all users
            users = self.db.get_all_watchlist_users()
            for user_id in users:
                await self._send_alert_to_user(user_id, message, None)
                
        except Exception as e:
            logger.error(f"Error sending consensus alert: {e}")
    
    def _get_chain_id(self, chain: str) -> int:
        """Get chain ID for Covalent API"""
        chain_ids = {
            'ethereum': 1,
            'bsc': 56
        }
        return chain_ids.get(chain, 1)

# Global monitor instance
watchlist_monitor = WatchlistMonitor()