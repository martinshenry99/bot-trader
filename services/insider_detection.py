"""Enhanced insider detection system"""
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import asyncio

from services.risk_scorer import RiskScorer
from services.market_research import MarketResearch
from integrations.covalent import CovalentAPI
from utils.notifications import send_alert

logger = logging.getLogger(__name__)

class InsiderDetection:
    """Enhanced system for detecting insider trading patterns"""
    
    def __init__(
        self,
        market_research: MarketResearch,
        risk_scorer: RiskScorer,
        covalent_api: CovalentAPI
    ):
        self.market_research = market_research
        self.risk_scorer = risk_scorer
        self.covalent = covalent_api
        
        # Historical data cache
        self._wallet_history: Dict[str, List[Dict]] = {}
        self._token_history: Dict[str, List[Dict]] = {}
        
        # Scoring thresholds
        self.thresholds = {
            'min_trades': 3,           # Minimum trades to consider pattern
            'success_rate': 0.65,      # Required win rate
            'time_window': 300,        # Seconds to group related trades
            'pump_threshold': 0.15,    # 15% price increase
            'group_size': 3,           # Minimum wallets in coordinated group
            'confidence_high': 0.8,    # High confidence threshold
            'confidence_medium': 0.6    # Medium confidence threshold
        }
    
    async def analyze_wallet(
        self,
        wallet_address: str,
        chain: str
    ) -> Dict:
        """Analyze wallet for insider trading patterns"""
        try:
            # Get historical trades
            trades = await self._get_wallet_trades(wallet_address, chain)
            
            # Analyze trade patterns
            pattern_score = await self._analyze_trade_patterns(trades)
            
            # Check for coordinated trading
            coordination_score = await self._check_coordination(
                wallet_address,
                trades,
                chain
            )
            
            # Calculate overall confidence
            confidence_score = (pattern_score + coordination_score) / 2
            
            # Determine confidence level
            confidence_level = self._get_confidence_level(confidence_score)
            
            return {
                'wallet_address': wallet_address,
                'chain': chain,
                'confidence_score': confidence_score,
                'confidence_level': confidence_level,
                'pattern_score': pattern_score,
                'coordination_score': coordination_score,
                'analysis_time': datetime.utcnow().isoformat(),
                'trade_count': len(trades),
                'successful_trades': sum(
                    1 for t in trades if t.get('profitable', False)
                )
            }
            
        except Exception as e:
            logger.error(f"Error analyzing wallet: {str(e)}")
            raise
    
    async def detect_insider_groups(
        self,
        token_address: str,
        chain: str,
        time_window: int = 3600  # 1 hour default
    ) -> List[Dict]:
        """Detect groups of coordinated insider trading"""
        try:
            # Get recent trades
            trades = await self._get_token_trades(
                token_address,
                chain,
                time_window
            )
            
            # Group trades by time windows
            trade_groups = self._group_trades_by_time(
                trades,
                self.thresholds['time_window']
            )
            
            insider_groups = []
            
            for group in trade_groups:
                # Skip small groups
                if len(group) < self.thresholds['group_size']:
                    continue
                
                # Analyze group behavior
                group_analysis = await self._analyze_group_behavior(
                    group,
                    token_address,
                    chain
                )
                
                if group_analysis['confidence_score'] >= self.thresholds['confidence_medium']:
                    insider_groups.append(group_analysis)
            
            return insider_groups
            
        except Exception as e:
            logger.error(f"Error detecting insider groups: {str(e)}")
            raise
    
    async def _get_wallet_trades(
        self,
        wallet_address: str,
        chain: str
    ) -> List[Dict]:
        """Get historical trades for a wallet"""
        try:
            # Check cache first
            if wallet_address in self._wallet_history:
                return self._wallet_history[wallet_address]
            
            # Get trades from API
            trades = await self.covalent.get_wallet_transactions(
                wallet_address,
                chain
            )
            
            # Process and cache trades
            processed_trades = []
            
            for trade in trades:
                # Get price data
                price_data = await self._get_price_data(
                    trade['token_address'],
                    trade['timestamp']
                )
                
                # Calculate profitability
                if price_data and trade.get('type') == 'buy':
                    future_price = await self._get_future_price(
                        trade['token_address'],
                        trade['timestamp']
                    )
                    trade['profitable'] = (
                        future_price > price_data['price'] * (1 + self.thresholds['pump_threshold'])
                    )
                
                processed_trades.append(trade)
            
            # Cache results
            self._wallet_history[wallet_address] = processed_trades
            
            return processed_trades
            
        except Exception as e:
            logger.error(f"Error getting wallet trades: {str(e)}")
            raise
    
    async def _get_token_trades(
        self,
        token_address: str,
        chain: str,
        time_window: int
    ) -> List[Dict]:
        """Get recent trades for a token"""
        try:
            # Calculate time range
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(seconds=time_window)
            
            # Get trades from API
            trades = await self.covalent.get_token_transactions(
                token_address,
                chain,
                start_time,
                end_time
            )
            
            return trades
            
        except Exception as e:
            logger.error(f"Error getting token trades: {str(e)}")
            raise
    
    async def _analyze_trade_patterns(self, trades: List[Dict]) -> float:
        """Analyze trading patterns for insider behavior"""
        try:
            if len(trades) < self.thresholds['min_trades']:
                return 0.0
            
            # Calculate success rate
            successful_trades = sum(
                1 for t in trades if t.get('profitable', False)
            )
            success_rate = successful_trades / len(trades)
            
            # Calculate timing score
            timing_scores = []
            
            for trade in trades:
                if trade.get('type') == 'buy':
                    # Check if bought before significant price increase
                    price_impact = await self._calculate_price_impact(
                        trade['token_address'],
                        trade['timestamp']
                    )
                    
                    if price_impact > self.thresholds['pump_threshold']:
                        timing_scores.append(1.0)
                    else:
                        timing_scores.append(0.0)
            
            timing_score = (
                sum(timing_scores) / len(timing_scores)
                if timing_scores else 0.0
            )
            
            # Weight different factors
            pattern_score = (
                success_rate * 0.6 +    # Weight success rate more heavily
                timing_score * 0.4      # Consider timing as supporting factor
            )
            
            return pattern_score
            
        except Exception as e:
            logger.error(f"Error analyzing trade patterns: {str(e)}")
            raise
    
    async def _check_coordination(
        self,
        wallet_address: str,
        trades: List[Dict],
        chain: str
    ) -> float:
        """Check for coordinated trading with other wallets"""
        try:
            coordination_scores = []
            
            for trade in trades:
                if trade.get('type') == 'buy':
                    # Find related trades in same time window
                    related_trades = await self._find_related_trades(
                        trade['token_address'],
                        trade['timestamp'],
                        chain,
                        exclude_wallet=wallet_address
                    )
                    
                    # Calculate coordination score for this trade
                    if len(related_trades) >= self.thresholds['group_size']:
                        # Check if trades are similarly sized
                        size_similarity = self._calculate_trade_similarity(
                            trade['amount'],
                            [t['amount'] for t in related_trades]
                        )
                        
                        # Check if trades are closely timed
                        timing_similarity = self._calculate_timing_similarity(
                            trade['timestamp'],
                            [t['timestamp'] for t in related_trades]
                        )
                        
                        trade_score = (
                            size_similarity * 0.4 +    # Similar trade sizes
                            timing_similarity * 0.6    # Close timing more important
                        )
                        
                        coordination_scores.append(trade_score)
            
            return (
                sum(coordination_scores) / len(coordination_scores)
                if coordination_scores else 0.0
            )
            
        except Exception as e:
            logger.error(f"Error checking coordination: {str(e)}")
            raise
    
    def _group_trades_by_time(
        self,
        trades: List[Dict],
        window: int
    ) -> List[List[Dict]]:
        """Group trades that occurred within the same time window"""
        try:
            if not trades:
                return []
            
            # Sort trades by timestamp
            sorted_trades = sorted(
                trades,
                key=lambda x: x['timestamp']
            )
            
            groups = []
            current_group = [sorted_trades[0]]
            group_start = sorted_trades[0]['timestamp']
            
            for trade in sorted_trades[1:]:
                # Check if trade is within window
                if (trade['timestamp'] - group_start).total_seconds() <= window:
                    current_group.append(trade)
                else:
                    # Start new group
                    if len(current_group) >= self.thresholds['group_size']:
                        groups.append(current_group)
                    current_group = [trade]
                    group_start = trade['timestamp']
            
            # Add last group if it meets size threshold
            if len(current_group) >= self.thresholds['group_size']:
                groups.append(current_group)
            
            return groups
            
        except Exception as e:
            logger.error(f"Error grouping trades: {str(e)}")
            raise
    
    async def _analyze_group_behavior(
        self,
        trades: List[Dict],
        token_address: str,
        chain: str
    ) -> Dict:
        """Analyze behavior of a potential insider group"""
        try:
            # Get unique wallets
            wallets = {t['wallet_address'] for t in trades}
            
            # Analyze each wallet
            wallet_scores = []
            
            for wallet in wallets:
                wallet_analysis = await self.analyze_wallet(wallet, chain)
                wallet_scores.append(wallet_analysis['confidence_score'])
            
            # Calculate group metrics
            avg_score = sum(wallet_scores) / len(wallet_scores)
            trade_similarity = self._calculate_trade_similarity(
                trades[0]['amount'],
                [t['amount'] for t in trades[1:]]
            )
            
            # Calculate overall confidence
            confidence_score = (
                avg_score * 0.5 +           # Individual wallet scores
                trade_similarity * 0.3 +     # Similar trade sizes
                (len(wallets) / 10) * 0.2    # Group size factor (max 10)
            )
            
            return {
                'token_address': token_address,
                'chain': chain,
                'wallet_count': len(wallets),
                'trade_count': len(trades),
                'confidence_score': confidence_score,
                'confidence_level': self._get_confidence_level(confidence_score),
                'avg_wallet_score': avg_score,
                'trade_similarity': trade_similarity,
                'detection_time': datetime.utcnow().isoformat(),
                'wallets': list(wallets)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing group behavior: {str(e)}")
            raise
    
    def _calculate_trade_similarity(
        self,
        base_amount: Decimal,
        amounts: List[Decimal]
    ) -> float:
        """Calculate similarity of trade amounts"""
        try:
            similarities = []
            
            for amount in amounts:
                # Calculate relative difference
                diff = abs(base_amount - amount) / max(base_amount, amount)
                similarity = 1 - min(diff, 1)  # Cap at 1.0
                similarities.append(similarity)
            
            return sum(similarities) / len(similarities)
            
        except Exception as e:
            logger.error(f"Error calculating trade similarity: {str(e)}")
            return 0.0
    
    def _calculate_timing_similarity(
        self,
        base_time: datetime,
        timestamps: List[datetime]
    ) -> float:
        """Calculate similarity of trade timing"""
        try:
            similarities = []
            
            for timestamp in timestamps:
                # Calculate time difference in seconds
                diff = abs((base_time - timestamp).total_seconds())
                # Convert to similarity score (0-1)
                similarity = max(
                    0,
                    1 - (diff / self.thresholds['time_window'])
                )
                similarities.append(similarity)
            
            return sum(similarities) / len(similarities)
            
        except Exception as e:
            logger.error(f"Error calculating timing similarity: {str(e)}")
            return 0.0
    
    def _get_confidence_level(self, score: float) -> str:
        """Convert confidence score to level"""
        if score >= self.thresholds['confidence_high']:
            return "High"
        elif score >= self.thresholds['confidence_medium']:
            return "Medium"
        else:
            return "Low"
    
    async def _get_price_data(
        self,
        token_address: str,
        timestamp: datetime
    ) -> Optional[Dict]:
        """Get historical price data for a token"""
        try:
            # Use market research service
            price_data = await self.market_research.get_historical_price(
                token_address,
                timestamp
            )
            return price_data
            
        except Exception as e:
            logger.error(f"Error getting price data: {str(e)}")
            return None
    
    async def _get_future_price(
        self,
        token_address: str,
        timestamp: datetime,
        lookforward: int = 3600  # 1 hour default
    ) -> Optional[Decimal]:
        """Get token price after specified time period"""
        try:
            future_time = timestamp + timedelta(seconds=lookforward)
            price_data = await self._get_price_data(
                token_address,
                future_time
            )
            
            return price_data['price'] if price_data else None
            
        except Exception as e:
            logger.error(f"Error getting future price: {str(e)}")
            return None
    
    async def _calculate_price_impact(
        self,
        token_address: str,
        timestamp: datetime,
        window: int = 3600  # 1 hour default
    ) -> float:
        """Calculate price impact after trade"""
        try:
            # Get prices before and after
            price_before = await self._get_price_data(
                token_address,
                timestamp
            )
            price_after = await self._get_future_price(
                token_address,
                timestamp,
                window
            )
            
            if price_before and price_after:
                return (
                    (price_after - price_before['price']) /
                    price_before['price']
                )
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating price impact: {str(e)}")
            return 0.0
