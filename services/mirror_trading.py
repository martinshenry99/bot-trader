
"""
Mirror Trading Service with Auto-Sell Logic
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

from core.execution_engine import execution_engine
from services.wallet_analyzer import wallet_analyzer
from integrations.helius import helius_client
from utils.key_manager import key_manager
from db import get_db_session, WalletWatch, MirrorTrade

logger = logging.getLogger(__name__)


@dataclass
class MirrorSettings:
    """Mirror trading configuration"""
    auto_sell_enabled: bool = True
    safe_mode_enabled: bool = False
    max_position_size_usd: float = 1000.0
    min_liquidity_usd: float = 10000.0
    max_slippage_percent: float = 5.0
    copy_percentage: float = 100.0  # % of watched wallet's position to copy


class MirrorTradingService:
    """Enhanced mirror trading with auto-sell functionality"""
    
    def __init__(self):
        self.settings = MirrorSettings()
        self.watched_wallets: Set[str] = set()
        self.active_positions: Dict[str, Dict] = {}  # token_address -> position_data
        self.is_monitoring = False
        self.last_scan_time = datetime.utcnow()
        
    async def start_mirror_trading(self, watched_wallets: List[str]):
        """Start monitoring watched wallets for mirror trading"""
        try:
            self.watched_wallets = set(watched_wallets)
            self.is_monitoring = True
            
            logger.info(f"🪞 Starting mirror trading for {len(watched_wallets)} wallets")
            
            # Start monitoring loop
            asyncio.create_task(self.monitor_watched_wallets())
            
        except Exception as e:
            logger.error(f"Failed to start mirror trading: {e}")
    
    async def stop_mirror_trading(self):
        """Stop mirror trading monitoring"""
        self.is_monitoring = False
        self.watched_wallets.clear()
        logger.info("🛑 Mirror trading stopped")
    
    async def monitor_watched_wallets(self):
        """Main monitoring loop for watched wallets"""
        while self.is_monitoring:
            try:
                for wallet_address in self.watched_wallets:
                    await self._check_wallet_activity(wallet_address)
                    await asyncio.sleep(1)  # Rate limiting
                
                # Check every 30 seconds
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Mirror trading monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _check_wallet_activity(self, wallet_address: str):
        """Check individual wallet for new trading activity"""
        try:
            # Get recent transactions
            recent_txs = await helius_client.monitor_wallet_activity(wallet_address)
            
            for tx in recent_txs:
                await self._process_mirror_transaction(tx, wallet_address)
                
        except Exception as e:
            logger.error(f"Failed to check wallet activity {wallet_address}: {e}")
    
    async def _process_mirror_transaction(self, transaction: Dict, source_wallet: str):
        """Process transaction for mirror trading"""
        try:
            tx_type = transaction.get('type')
            
            if tx_type == 'SWAP':
                # Determine if it's a buy or sell
                input_mint = transaction.get('inputMint')
                output_mint = transaction.get('outputMint')
                
                # Check if selling a token we're watching
                if self._is_sell_transaction(transaction):
                    await self._handle_mirror_sell(transaction, source_wallet)
                elif self._is_buy_transaction(transaction):
                    await self._handle_mirror_buy(transaction, source_wallet)
                    
        except Exception as e:
            logger.error(f"Failed to process mirror transaction: {e}")
    
    def _is_sell_transaction(self, transaction: Dict) -> bool:
        """Determine if transaction is a sell (token -> SOL/USDC)"""
        output_mint = transaction.get('outputMint')
        # Check if output is SOL or USDC (common sell targets)
        return output_mint in ['So11111111111111111111111111111111111111112', 
                              'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v']
    
    def _is_buy_transaction(self, transaction: Dict) -> bool:
        """Determine if transaction is a buy (SOL/USDC -> token)"""
        input_mint = transaction.get('inputMint')
        # Check if input is SOL or USDC
        return input_mint in ['So11111111111111111111111111111111111111112',
                             'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v']
    
    async def _handle_mirror_sell(self, transaction: Dict, source_wallet: str):
        """Handle mirror sell - auto-sell if we have position"""
        try:
            token_mint = transaction.get('inputMint')
            
            # Check if we have position in this token
            if token_mint in self.active_positions:
                position = self.active_positions[token_mint]
                
                if self.settings.auto_sell_enabled:
                    logger.info(f"🔴 Auto-sell triggered for {token_mint}")
                    
                    # Execute sell order
                    await self._execute_mirror_sell(token_mint, position, source_wallet)
                else:
                    logger.info(f"📢 Sell signal detected for {token_mint} (auto-sell disabled)")
                    # Send alert to user
                    await self._send_sell_alert(token_mint, source_wallet)
                    
        except Exception as e:
            logger.error(f"Mirror sell handling failed: {e}")
    
    async def _handle_mirror_buy(self, transaction: Dict, source_wallet: str):
        """Handle mirror buy - send alert for manual confirmation"""
        try:
            token_mint = transaction.get('outputMint')
            amount_usd = transaction.get('amountUsd', 0)
            
            # Perform safety checks in safe mode
            if self.settings.safe_mode_enabled:
                safety_check = await self._perform_safety_checks(token_mint)
                if not safety_check['is_safe']:
                    logger.warning(f"⚠️ Safety check failed for {token_mint}: {safety_check['reason']}")
                    return
            
            # Send buy alert
            await self._send_buy_alert(token_mint, source_wallet, amount_usd)
            
        except Exception as e:
            logger.error(f"Mirror buy handling failed: {e}")
    
    async def _execute_mirror_sell(self, token_mint: str, position: Dict, source_wallet: str):
        """Execute mirror sell order"""
        try:
            # Get current position size
            position_size = position.get('amount', 0)
            
            if position_size <= 0:
                logger.warning(f"No position to sell for {token_mint}")
                return
            
            # Execute sell via Jupiter
            trade_params = {
                'chain': 'solana',
                'input_mint': token_mint,
                'output_mint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
                'amount': int(position_size),
                'wallet_keypair': position.get('wallet_keypair'),
                'slippage_bps': int(self.settings.max_slippage_percent * 100)
            }
            
            result = await execution_engine.execute_trade(trade_params)
            
            if result['success']:
                # Update position
                del self.active_positions[token_mint]
                
                # Log mirror trade
                await self._log_mirror_trade(token_mint, 'SELL', result, source_wallet)
                
                logger.info(f"✅ Mirror sell executed for {token_mint}: {result['tx_hash']}")
            else:
                logger.error(f"❌ Mirror sell failed for {token_mint}: {result['error']}")
                
        except Exception as e:
            logger.error(f"Mirror sell execution failed: {e}")
    
    async def _perform_safety_checks(self, token_mint: str) -> Dict:
        """Perform safety checks before executing trades"""
        try:
            # Honeypot check via Jupiter simulation
            simulation = await jupiter_client.simulate_swap(
                'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
                token_mint,
                1000000  # 1 USDC
            )
            
            if simulation.get('is_honeypot'):
                return {
                    'is_safe': False,
                    'reason': 'Honeypot detected'
                }
            
            # Price impact check
            price_impact = simulation.get('price_impact', 0)
            if price_impact > 10:  # 10% price impact
                return {
                    'is_safe': False,
                    'reason': f'High price impact: {price_impact}%'
                }
            
            # Liquidity check
            token_metadata = await helius_client.get_token_metadata(token_mint)
            if not token_metadata:
                return {
                    'is_safe': False,
                    'reason': 'Token metadata not found'
                }
            
            return {
                'is_safe': True,
                'reason': 'All safety checks passed'
            }
            
        except Exception as e:
            logger.error(f"Safety checks failed: {e}")
            return {
                'is_safe': False,
                'reason': f'Safety check error: {e}'
            }
    
    async def _send_buy_alert(self, token_mint: str, source_wallet: str, amount_usd: float):
        """Send buy alert to user"""
        try:
            # This would integrate with your Telegram bot
            alert_message = (
                f"🟢 BUY SIGNAL DETECTED\n"
                f"Token: {token_mint[:8]}...\n"
                f"Source: {source_wallet[:8]}...\n"
                f"Amount: ${amount_usd:,.2f}\n"
                f"Time: {datetime.utcnow().strftime('%H:%M:%S')}"
            )
            
            logger.info(alert_message)
            # TODO: Send to Telegram
            
        except Exception as e:
            logger.error(f"Failed to send buy alert: {e}")
    
    async def _send_sell_alert(self, token_mint: str, source_wallet: str):
        """Send sell alert to user"""
        try:
            alert_message = (
                f"🔴 SELL SIGNAL DETECTED\n"
                f"Token: {token_mint[:8]}...\n"
                f"Source: {source_wallet[:8]}...\n"
                f"Time: {datetime.utcnow().strftime('%H:%M:%S')}\n"
                f"Auto-sell: {'ON' if self.settings.auto_sell_enabled else 'OFF'}"
            )
            
            logger.info(alert_message)
            # TODO: Send to Telegram
            
        except Exception as e:
            logger.error(f"Failed to send sell alert: {e}")
    
    async def _log_mirror_trade(self, token_mint: str, action: str, result: Dict, source_wallet: str):
        """Log mirror trade to database"""
        try:
            db = next(get_db_session())
            
            mirror_trade = MirrorTrade(
                source_wallet=source_wallet,
                token_address=token_mint,
                action=action,
                tx_hash=result.get('tx_hash'),
                amount_usd=result.get('amount_usd', 0),
                timestamp=datetime.utcnow(),
                success=result.get('success', False),
                error_message=result.get('error')
            )
            
            db.add(mirror_trade)
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log mirror trade: {e}")
        finally:
            db.close()
    
    def update_settings(self, **kwargs):
        """Update mirror trading settings"""
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
                logger.info(f"Updated mirror setting {key}: {value}")


# Global mirror trading service
mirror_trading_service = MirrorTradingService()
