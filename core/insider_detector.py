"""
Enhanced insider detection with correlation analysis and group buy detection
"""
from typing import Dict, List, Set, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
from decimal import Decimal
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)

@dataclass
class InsiderTrade:
    """Represents an insider trade"""
    wallet: str
    token: str
    action: str  # 'BUY' or 'SELL'
    amount_usd: Decimal
    timestamp: datetime
    profit: Optional[Decimal] = None
    win: Optional[bool] = None

@dataclass
class InsiderMetrics:
    """Wallet performance metrics"""
    win_rate: float
    avg_roi: float
    max_profit: float
    trade_count: int
    correlation_score: float
    group_score: float
    confidence: float

class InsiderDetector:
    """Advanced insider detection system"""
    
    def __init__(
        self,
        min_trades: int = 10,
        min_win_rate: float = 0.65,
        min_roi: float = 50.0,
        correlation_threshold: float = 0.7,
        group_buy_window: int = 300,  # 5 minutes
        group_buy_threshold: int = 3
    ):
        self.min_trades = min_trades
        self.min_win_rate = min_win_rate
        self.min_roi = min_roi
        self.correlation_threshold = correlation_threshold
        self.group_buy_window = group_buy_window
        self.group_buy_threshold = group_buy_threshold
        
        # Cache for performance
        self._wallet_metrics: Dict[str, InsiderMetrics] = {}
        self._recent_trades: List[InsiderTrade] = []
        self._token_price_history: Dict[str, List[tuple]] = {}
        
        # Group buy detection
        self._active_group_buys: Dict[str, List[InsiderTrade]] = {}
    
    async def process_trade(
        self,
        trade: InsiderTrade
    ) -> Optional[Dict[str, Any]]:
        """Process a new trade and detect insider activity"""
        try:
            # Update recent trades
            self._recent_trades.append(trade)
            self._cleanup_old_trades()
            
            # Check for group buys
            group_buy = self._check_group_buy(trade)
            
            # Get wallet metrics
            metrics = await self._get_wallet_metrics(trade.wallet)
            if not metrics:
                return None
            
            # Calculate confidence score
            confidence = self._calculate_confidence(
                metrics,
                group_buy
            )
            
            if confidence >= 0.7:  # High confidence threshold
                return {
                    'trade': trade,
                    'metrics': metrics,
                    'group_buy': group_buy,
                    'confidence': confidence,
                    'flags': self._generate_flags(
                        metrics,
                        group_buy,
                        confidence
                    )
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing trade: {e}")
            return None
    
    def _check_group_buy(
        self,
        trade: InsiderTrade
    ) -> Dict[str, Any]:
        """Detect group buy patterns"""
        if trade.action != 'BUY':
            return {}
            
        # Clean old group buys
        self._cleanup_group_buys()
        
        # Check existing group
        if trade.token in self._active_group_buys:
            group = self._active_group_buys[trade.token]
            group.append(trade)
            
            if len(group) >= self.group_buy_threshold:
                return {
                    'detected': True,
                    'wallets': len(group),
                    'total_usd': sum(
                        t.amount_usd for t in group
                    ),
                    'first_trade': group[0].timestamp,
                    'latest_trade': trade.timestamp
                }
        else:
            # Start new group
            self._active_group_buys[trade.token] = [trade]
        
        return {}
    
    async def _get_wallet_metrics(
        self,
        wallet: str
    ) -> Optional[InsiderMetrics]:
        """Get or calculate wallet metrics"""
        # Check cache first
        if wallet in self._wallet_metrics:
            return self._wallet_metrics[wallet]
            
        # Get historical trades
        trades = await self._get_wallet_trades(wallet)
        if len(trades) < self.min_trades:
            return None
        
        # Calculate basic metrics
        wins = sum(1 for t in trades if t.win)
        win_rate = wins / len(trades)
        
        if win_rate < self.min_win_rate:
            return None
            
        # Calculate ROI
        roi_list = [
            float(t.profit or 0)
            for t in trades
            if t.profit is not None
        ]
        avg_roi = sum(roi_list) / len(roi_list)
        
        if avg_roi < self.min_roi:
            return None
            
        # Calculate correlation score
        correlation = self._calculate_correlation(trades)
        
        # Calculate group participation
        group_score = self._calculate_group_score(wallet)
        
        # Create metrics
        metrics = InsiderMetrics(
            win_rate=win_rate,
            avg_roi=avg_roi,
            max_profit=max(roi_list),
            trade_count=len(trades),
            correlation_score=correlation,
            group_score=group_score,
            confidence=0.0  # Will be set later
        )
        
        # Cache results
        self._wallet_metrics[wallet] = metrics
        
        return metrics
    
    def _calculate_correlation(
        self,
        trades: List[InsiderTrade]
    ) -> float:
        """Calculate historical correlation with price movements"""
        try:
            correlations = []
            
            for trade in trades:
                if trade.token in self._token_price_history:
                    # Get price history around trade
                    prices = self._token_price_history[trade.token]
                    trade_idx = self._find_nearest_price_index(
                        prices,
                        trade.timestamp
                    )
                    
                    if trade_idx is not None:
                        # Get price changes before and after trade
                        pre_trade = self._calculate_returns(
                            prices,
                            max(0, trade_idx - 100),
                            trade_idx
                        )
                        post_trade = self._calculate_returns(
                            prices,
                            trade_idx,
                            min(len(prices), trade_idx + 100)
                        )
                        
                        if pre_trade and post_trade:
                            correlation = stats.pearsonr(
                                pre_trade,
                                post_trade
                            )[0]
                            correlations.append(correlation)
            
            return np.mean(correlations) if correlations else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating correlation: {e}")
            return 0.0
    
    def _calculate_group_score(self, wallet: str) -> float:
        """Calculate wallet's group participation score"""
        try:
            participations = 0
            total_groups = 0
            
            for group in self._active_group_buys.values():
                if len(group) >= self.group_buy_threshold:
                    total_groups += 1
                    if any(t.wallet == wallet for t in group):
                        participations += 1
            
            return (
                participations / total_groups
                if total_groups > 0
                else 0.0
            )
            
        except Exception as e:
            logger.error(f"Error calculating group score: {e}")
            return 0.0
    
    def _calculate_confidence(
        self,
        metrics: InsiderMetrics,
        group_buy: Dict[str, Any]
    ) -> float:
        """Calculate overall confidence score"""
        try:
            # Base confidence from win rate and ROI
            base_confidence = (
                0.4 * (metrics.win_rate / self.min_win_rate) +
                0.3 * (metrics.avg_roi / self.min_roi)
            )
            
            # Adjust for correlation and group activity
            correlation_boost = (
                0.2 *
                (metrics.correlation_score / self.correlation_threshold)
            )
            
            group_boost = 0.0
            if group_buy.get('detected'):
                group_boost = 0.1 * (
                    group_buy['wallets'] / self.group_buy_threshold
                )
            
            # Calculate final score
            confidence = min(
                1.0,
                base_confidence + correlation_boost + group_boost
            )
            
            # Update metrics
            metrics.confidence = confidence
            
            return confidence
            
        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return 0.0
    
    def _generate_flags(
        self,
        metrics: InsiderMetrics,
        group_buy: Dict[str, Any],
        confidence: float
    ) -> List[str]:
        """Generate human-readable warning flags"""
        flags = []
        
        # Win rate flag
        if metrics.win_rate >= 0.8:
            flags.append("🎯 Extremely High Win Rate")
        elif metrics.win_rate >= 0.7:
            flags.append("📈 Strong Win Rate")
        
        # ROI flags
        if metrics.avg_roi >= 100:
            flags.append("💰 Exceptional Returns")
        elif metrics.avg_roi >= 75:
            flags.append("💵 High Returns")
        
        # Correlation flags
        if metrics.correlation_score >= 0.8:
            flags.append("🎯 Strong Price Correlation")
        elif metrics.correlation_score >= 0.6:
            flags.append("📊 Notable Price Impact")
        
        # Group buy flags
        if group_buy.get('detected'):
            flags.append(
                f"👥 Group Buy Detected "
                f"({group_buy['wallets']} wallets)"
            )
        
        # Confidence level
        if confidence >= 0.9:
            flags.append("⚠️ CRITICAL: Very High Confidence")
        elif confidence >= 0.8:
            flags.append("⚠️ High Confidence Signal")
        elif confidence >= 0.7:
            flags.append("ℹ️ Medium Confidence Signal")
        
        return flags
    
    def _cleanup_old_trades(self):
        """Remove trades older than window"""
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        self._recent_trades = [
            t for t in self._recent_trades
            if t.timestamp >= cutoff
        ]
    
    def _cleanup_group_buys(self):
        """Remove expired group buys"""
        cutoff = datetime.utcnow() - timedelta(
            seconds=self.group_buy_window
        )
        expired = set()
        
        for token, group in self._active_group_buys.items():
            valid_trades = [
                t for t in group
                if t.timestamp >= cutoff
            ]
            if valid_trades:
                self._active_group_buys[token] = valid_trades
            else:
                expired.add(token)
        
        for token in expired:
            del self._active_group_buys[token]
    
    async def _get_wallet_trades(
        self,
        wallet: str
    ) -> List[InsiderTrade]:
        """Get wallet's historical trades"""
        # This would be implemented to fetch from your database
        pass
    
    def _find_nearest_price_index(
        self,
        prices: List[tuple],
        timestamp: datetime
    ) -> Optional[int]:
        """Find nearest price point to timestamp"""
        for i, (price_time, _) in enumerate(prices):
            if abs(price_time - timestamp) < timedelta(minutes=1):
                return i
        return None
    
    def _calculate_returns(
        self,
        prices: List[tuple],
        start: int,
        end: int
    ) -> List[float]:
        """Calculate return series for price range"""
        if end <= start + 1:
            return []
            
        returns = []
        for i in range(start + 1, end):
            prev_price = prices[i-1][1]
            curr_price = prices[i][1]
            if prev_price > 0:
                returns.append(
                    (curr_price - prev_price) / prev_price
                )
        
        return returns
