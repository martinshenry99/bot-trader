"""
Advanced trading engine with mirror trading and risk management
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from decimal import Decimal

from integrations.base import integration_manager
from core.wallet_manager import wallet_manager
from db import get_db_session, Trade, User, Token

logger = logging.getLogger(__name__)


class TradeType(Enum):
    BUY = "buy"
    SELL = "sell"
    MIRROR_BUY = "mirror_buy"
    MIRROR_SELL = "mirror_sell"
    PANIC_SELL = "panic_sell"


class RiskLevel(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TradeSignal:
    """Trading signal from wallet monitoring"""
    source_wallet: str
    token_address: str
    action: str  # 'buy' or 'sell'
    amount: float
    price_usd: float
    transaction_hash: str
    blockchain: str
    timestamp: datetime
    confidence: float = 1.0


@dataclass
class RiskAssessment:
    """Risk assessment for a trade"""
    risk_level: RiskLevel
    risk_score: float
    factors: List[str]
    recommendations: List[str]
    is_safe_to_trade: bool
    max_trade_amount: float


class TradingEngine:
    """Advanced trading engine with mirror trading capabilities"""
    
    def __init__(self):
        self.config = {
            'safe_mode': True,
            'mirror_sell_enabled': True,
            'mirror_buy_enabled': False,
            'max_auto_buy_usd': 50.0,
            'max_position_size_usd': 500.0,
            'max_slippage': 0.05,  # 5%
            'min_liquidity_usd': 10000.0,
            'blacklisted_tokens': set(),
            'blacklisted_wallets': set(),
            'trusted_wallets': set(),
            'moonshot_threshold': 200.0  # 200x multiplier
        }
        
        self.active_trades: Dict[str, Dict] = {}
        self.mirror_positions: Dict[str, Dict] = {}
        self.trade_history: List[Dict] = []
        
        # Performance tracking
        self.stats = {
            'total_trades': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'total_pnl_usd': 0.0,
            'win_rate': 0.0,
            'moonshots_detected': 0,
            'early_alerts_sent': 0
        }
    
    async def process_trade_signal(self, signal: TradeSignal, user_id: str) -> Dict[str, Any]:
        """
        Process incoming trade signal from wallet monitoring
        
        Args:
            signal: Trade signal data
            user_id: User ID to execute trade for
            
        Returns:
            Processing result
        """
        try:
            logger.info(f"Processing {signal.action} signal for {signal.token_address} from {signal.source_wallet}")
            
            # Check if wallet is blacklisted
            if signal.source_wallet.lower() in self.config['blacklisted_wallets']:
                logger.warning(f"Ignoring signal from blacklisted wallet: {signal.source_wallet}")
                return {'success': False, 'reason': 'blacklisted_wallet'}
            
            # Check if token is blacklisted
            if signal.token_address.lower() in self.config['blacklisted_tokens']:
                logger.warning(f"Ignoring signal for blacklisted token: {signal.token_address}")
                return {'success': False, 'reason': 'blacklisted_token'}
            
            # Process based on action type
            if signal.action == 'buy':
                return await self._process_buy_signal(signal, user_id)
            elif signal.action == 'sell':
                return await self._process_sell_signal(signal, user_id)
            else:
                logger.warning(f"Unknown signal action: {signal.action}")
                return {'success': False, 'reason': 'unknown_action'}
                
        except Exception as e:
            logger.error(f"Failed to process trade signal: {e}")
            return {'success': False, 'reason': 'processing_error', 'error': str(e)}
    
    async def _process_buy_signal(self, signal: TradeSignal, user_id: str) -> Dict[str, Any]:
        """Process buy signal with mirror trading logic"""
        try:
            # Mirror buy is disabled by default - ask user for confirmation
            if not self.config['mirror_buy_enabled']:
                # Send alert to user for manual decision
                await self._send_buy_alert(signal, user_id)
                return {
                    'success': True,
                    'action': 'alert_sent',
                    'message': 'Buy alert sent to user for manual decision'
                }
            
            # If mirror buy is enabled, perform risk assessment
            risk_assessment = await self._assess_trade_risk(signal.token_address, signal.blockchain)
            
            if not risk_assessment.is_safe_to_trade:
                logger.warning(f"Trade blocked due to risk assessment: {risk_assessment.risk_level}")
                await self._send_risk_alert(signal, risk_assessment, user_id)
                return {
                    'success': False,
                    'reason': 'risk_too_high',
                    'risk_assessment': risk_assessment.__dict__
                }
            
            # Calculate trade amount
            trade_amount_usd = min(
                self.config['max_auto_buy_usd'],
                risk_assessment.max_trade_amount
            )
            
            # Execute mirror buy
            result = await self._execute_mirror_buy(
                signal.token_address,
                trade_amount_usd,
                signal.blockchain,
                user_id,
                signal
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process buy signal: {e}")
            return {'success': False, 'reason': 'buy_processing_error', 'error': str(e)}
    
    async def _process_sell_signal(self, signal: TradeSignal, user_id: str) -> Dict[str, Any]:
        """Process sell signal with automatic mirror selling"""
        try:
            # Mirror sell is enabled by default
            if not self.config['mirror_sell_enabled']:
                logger.info("Mirror sell disabled, skipping")
                return {'success': False, 'reason': 'mirror_sell_disabled'}
            
            # Check if we have a position in this token
            position = await self._get_user_position(user_id, signal.token_address)
            if not position:
                logger.info(f"No position found for {signal.token_address}, skipping mirror sell")
                return {'success': False, 'reason': 'no_position'}
            
            # Execute mirror sell
            result = await self._execute_mirror_sell(
                signal.token_address,
                position['amount'],
                signal.blockchain,
                user_id,
                signal
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process sell signal: {e}")
            return {'success': False, 'reason': 'sell_processing_error', 'error': str(e)}
    
    async def _assess_trade_risk(self, token_address: str, blockchain: str) -> RiskAssessment:
        """
        Comprehensive risk assessment for trading decision
        
        Args:
            token_address: Token contract address
            blockchain: Blockchain network
            
        Returns:
            Risk assessment result
        """
        try:
            risk_factors = []
            risk_score = 0.0
            recommendations = []
            
            # Get GoPlus security analysis
            goplus_client = integration_manager.get_client('goplus')
            if goplus_client:
                chain_id = self._get_chain_id(blockchain)
                security_data = await goplus_client.check_token_security(str(chain_id), token_address)
                
                if security_data:
                    if security_data['is_honeypot']:
                        risk_score += 100
                        risk_factors.append('Confirmed honeypot')
                    
                    if security_data['risk_score'] > 50:
                        risk_score += security_data['risk_score'] * 0.5
                        risk_factors.extend(security_data['risk_factors'][:3])
                    
                    if security_data['buy_tax'] > 10:
                        risk_score += 20
                        risk_factors.append(f"High buy tax: {security_data['buy_tax']}%")
                    
                    if security_data['sell_tax'] > 10:
                        risk_score += 20
                        risk_factors.append(f"High sell tax: {security_data['sell_tax']}%")
            
            # Get CoinGecko market data
            coingecko_client = integration_manager.get_client('coingecko')
            if coingecko_client:
                token_info = await coingecko_client.get_token_info(token_address)
                if token_info:
                    market_cap = token_info.get('market_cap', 0)
                    volume_24h = token_info.get('total_volume', 0)
                    
                    if market_cap < 100000:  # Less than $100k market cap
                        risk_score += 30
                        risk_factors.append(f"Low market cap: ${market_cap:,.0f}")
                    
                    if volume_24h < 10000:  # Less than $10k daily volume
                        risk_score += 25
                        risk_factors.append(f"Low 24h volume: ${volume_24h:,.0f}")
                    
                    # Check price volatility
                    price_change_24h = token_info.get('price_change_24h', 0)
                    if abs(price_change_24h) > 50:
                        risk_score += 15
                        risk_factors.append(f"High volatility: {price_change_24h:+.1f}%")
            
            # Determine risk level
            if risk_score >= 80:
                risk_level = RiskLevel.CRITICAL
                is_safe = False
                max_amount = 0.0
            elif risk_score >= 60:
                risk_level = RiskLevel.HIGH
                is_safe = False if self.config['safe_mode'] else True
                max_amount = 10.0
            elif risk_score >= 40:
                risk_level = RiskLevel.MEDIUM
                is_safe = True
                max_amount = 25.0
            elif risk_score >= 20:
                risk_level = RiskLevel.LOW
                is_safe = True
                max_amount = 50.0
            else:
                risk_level = RiskLevel.SAFE
                is_safe = True
                max_amount = 100.0
            
            # Generate recommendations
            if risk_score > 50:
                recommendations.append("Consider avoiding this trade")
            elif risk_score > 30:
                recommendations.append("Use smaller position size")
            elif risk_score > 10:
                recommendations.append("Monitor closely after entry")
            else:
                recommendations.append("Low risk trade")
            
            if len(risk_factors) > 3:
                recommendations.append("Multiple risk factors detected")
            
            return RiskAssessment(
                risk_level=risk_level,
                risk_score=risk_score,
                factors=risk_factors,
                recommendations=recommendations,
                is_safe_to_trade=is_safe,
                max_trade_amount=max_amount
            )
            
        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            return RiskAssessment(
                risk_level=RiskLevel.CRITICAL,
                risk_score=100.0,
                factors=['Risk assessment failed'],
                recommendations=['Avoid trading'],
                is_safe_to_trade=False,
                max_trade_amount=0.0
            )
    
    async def execute_manual_buy(self, user_id: str, token_address: str, amount_usd: float, 
                                blockchain: str = 'ethereum') -> Dict[str, Any]:
        """
        Execute manual buy order from user command
        
        Args:
            user_id: User ID
            token_address: Token to buy
            amount_usd: USD amount to spend
            blockchain: Blockchain network
            
        Returns:
            Execution result
        """
        try:
            logger.info(f"Executing manual buy: {amount_usd} USD of {token_address}")
            
            # Risk assessment
            risk_assessment = await self._assess_trade_risk(token_address, blockchain)
            
            # Check if safe mode blocks the trade
            if self.config['safe_mode'] and not risk_assessment.is_safe_to_trade:
                return {
                    'success': False,
                    'reason': 'blocked_by_safe_mode',
                    'risk_assessment': risk_assessment.__dict__,
                    'message': f'Trade blocked by safe mode. Risk level: {risk_assessment.risk_level.value}'
                }
            
            # Validate amount
            max_amount = min(amount_usd, risk_assessment.max_trade_amount)
            if max_amount < amount_usd:
                logger.warning(f"Reducing trade amount from ${amount_usd} to ${max_amount} due to risk")
            
            # Execute the buy
            result = await self._execute_buy_order(
                token_address=token_address,
                amount_usd=max_amount,
                blockchain=blockchain,
                user_id=user_id,
                trade_type=TradeType.BUY
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Manual buy execution failed: {e}")
            return {'success': False, 'reason': 'execution_error', 'error': str(e)}
    
    async def execute_manual_sell(self, user_id: str, token_address: str, 
                                 amount_percentage: float = 100.0, blockchain: str = 'ethereum') -> Dict[str, Any]:
        """
        Execute manual sell order from user command
        
        Args:
            user_id: User ID
            token_address: Token to sell
            amount_percentage: Percentage of holdings to sell (default 100%)
            blockchain: Blockchain network
            
        Returns:
            Execution result
        """
        try:
            logger.info(f"Executing manual sell: {amount_percentage}% of {token_address}")
            
            # Get current position
            position = await self._get_user_position(user_id, token_address)
            if not position:
                return {
                    'success': False,
                    'reason': 'no_position',
                    'message': f'No position found for {token_address}'
                }
            
            # Calculate sell amount
            sell_amount = position['amount'] * (amount_percentage / 100.0)
            
            # Execute the sell
            result = await self._execute_sell_order(
                token_address=token_address,
                token_amount=sell_amount,
                blockchain=blockchain,
                user_id=user_id,
                trade_type=TradeType.SELL
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Manual sell execution failed: {e}")
            return {'success': False, 'reason': 'execution_error', 'error': str(e)}
    
    async def execute_panic_sell(self, user_id: str, blockchain: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute panic sell - liquidate all positions immediately
        
        Args:
            user_id: User ID
            blockchain: Specific blockchain or None for all
            
        Returns:
            Execution results for all positions
        """
        try:
            logger.warning(f"Executing PANIC SELL for user {user_id}")
            
            # Get all user positions
            positions = await self._get_all_user_positions(user_id, blockchain)
            
            if not positions:
                return {
                    'success': True,
                    'message': 'No positions to liquidate',
                    'liquidated_positions': []
                }
            
            results = []
            total_liquidated = 0
            
            # Liquidate each position
            for position in positions:
                try:
                    sell_result = await self._execute_sell_order(
                        token_address=position['token_address'],
                        token_amount=position['amount'],
                        blockchain=position['blockchain'],
                        user_id=user_id,
                        trade_type=TradeType.PANIC_SELL,
                        max_slippage=0.10  # Allow higher slippage for panic sells
                    )
                    
                    results.append({
                        'token_address': position['token_address'],
                        'amount': position['amount'],
                        'success': sell_result['success'],
                        'result': sell_result
                    })
                    
                    if sell_result['success']:
                        total_liquidated += 1
                        
                except Exception as e:
                    logger.error(f"Failed to liquidate {position['token_address']}: {e}")
                    results.append({
                        'token_address': position['token_address'],
                        'amount': position['amount'],
                        'success': False,
                        'error': str(e)
                    })
            
            return {
                'success': True,
                'total_positions': len(positions),
                'liquidated_count': total_liquidated,
                'results': results,
                'message': f'Panic sell completed: {total_liquidated}/{len(positions)} positions liquidated'
            }
            
        except Exception as e:
            logger.error(f"Panic sell failed: {e}")
            return {'success': False, 'reason': 'panic_sell_error', 'error': str(e)}
    
    def _get_chain_id(self, blockchain: str) -> int:
        """Get chain ID for blockchain name"""
        chain_mapping = {
            'ethereum': 1,
            'sepolia': 11155111,
            'bsc': 56,
            'bsc-testnet': 97,
            'polygon': 137,
            'avalanche': 43114
        }
        return chain_mapping.get(blockchain.lower(), 1)
    
    async def _get_user_position(self, user_id: str, token_address: str) -> Optional[Dict]:
        """Get user's current position for a token"""
        # This would query the database for current holdings
        # Placeholder implementation
        db = get_db_session()
        try:
            # Query for user's trades in this token to calculate position
            trades = db.query(Trade).filter(
                Trade.user_id == int(user_id),
                Trade.token_address == token_address.lower()
            ).all()
            
            if not trades:
                return None
            
            # Calculate net position
            total_bought = sum(trade.amount_out for trade in trades if trade.trade_type == 'buy')
            total_sold = sum(trade.amount_in for trade in trades if trade.trade_type == 'sell')
            
            net_amount = total_bought - total_sold
            
            if net_amount <= 0:
                return None
            
            return {
                'token_address': token_address,
                'amount': net_amount,
                'blockchain': 'ethereum',  # Would be stored in trades
                'avg_entry_price': 0.0  # Would calculate from trades
            }
            
        finally:
            db.close()
    
    async def _get_all_user_positions(self, user_id: str, blockchain: Optional[str] = None) -> List[Dict]:
        """Get all user positions"""
        # Placeholder - would implement proper position tracking
        return []
    
    # Additional helper methods would be implemented here...
    
    async def get_trading_stats(self, user_id: str) -> Dict[str, Any]:
        """Get trading statistics for user"""
        try:
            db = get_db_session()
            try:
                trades = db.query(Trade).filter(Trade.user_id == int(user_id)).all()
                
                if not trades:
                    return {
                        'total_trades': 0,
                        'successful_trades': 0,
                        'failed_trades': 0,
                        'win_rate': 0.0,
                        'total_pnl_usd': 0.0,
                        'best_trade': None,
                        'worst_trade': None
                    }
                
                successful_trades = [t for t in trades if t.status == 'confirmed']
                failed_trades = [t for t in trades if t.status == 'failed']
                
                win_rate = len(successful_trades) / len(trades) * 100 if trades else 0
                
                return {
                    'total_trades': len(trades),
                    'successful_trades': len(successful_trades),
                    'failed_trades': len(failed_trades),
                    'win_rate': win_rate,
                    'total_pnl_usd': 0.0,  # Would calculate from price differences
                    'best_trade': None,    # Would find best performing trade
                    'worst_trade': None    # Would find worst performing trade
                }
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to get trading stats: {e}")
            return {'error': str(e)}


# Global trading engine instance
trading_engine = TradingEngine()