"""Performance analytics and reporting service"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import statistics

from db.models.trade_log import TradingSession, TradeLog, TradeType, TradeStatus
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

class PerformanceAnalytics:
    """Service for analyzing trading performance and generating reports"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_portfolio_stats(
        self,
        wallet_address: str,
        timeframe: str = "all"
    ) -> Dict:
        """Get portfolio performance statistics"""
        try:
            # Build base query
            query = select(TradingSession).where(
                TradingSession.wallet_address == wallet_address
            )
            
            # Apply timeframe filter
            if timeframe != "all":
                days = self._timeframe_to_days(timeframe)
                cutoff = datetime.utcnow() - timedelta(days=days)
                query = query.where(TradingSession.start_time >= cutoff)
            
            # Execute query
            result = await self.session.execute(query)
            sessions = result.scalars().all()
            
            if not sessions:
                return self._empty_portfolio_stats()
            
            # Calculate metrics
            total_investment = sum(s.initial_investment for s in sessions)
            total_final = sum(s.final_value for s in sessions if s.final_value)
            total_profit = total_final - total_investment if total_final else Decimal('0')
            
            # ROI calculations
            rois = [
                ((s.final_value - s.initial_investment) / s.initial_investment * 100)
                for s in sessions
                if s.final_value and s.initial_investment > 0
            ]
            
            avg_roi = statistics.mean(rois) if rois else 0
            roi_std = statistics.stdev(rois) if len(rois) > 1 else 0
            
            # Win rate calculation
            profitable = sum(1 for roi in rois if roi > 0)
            win_rate = (profitable / len(rois) * 100) if rois else 0
            
            # Get all trades
            trade_query = select(TradeLog).where(
                TradeLog.session_id.in_([s.id for s in sessions])
            )
            trade_result = await self.session.execute(trade_query)
            trades = trade_result.scalars().all()
            
            return {
                'overview': {
                    'total_sessions': len(sessions),
                    'total_trades': len(trades),
                    'active_sessions': sum(1 for s in sessions if s.is_active),
                    'total_investment': str(total_investment),
                    'total_final_value': str(total_final),
                    'total_profit_loss': str(total_profit)
                },
                'performance': {
                    'win_rate': float(win_rate),
                    'average_roi': float(avg_roi),
                    'roi_volatility': float(roi_std),
                    'best_roi': float(max(rois)) if rois else 0,
                    'worst_roi': float(min(rois)) if rois else 0
                },
                'risk_metrics': await self._calculate_risk_metrics(sessions),
                'trade_metrics': self._calculate_trade_metrics(trades)
            }
            
        except Exception as e:
            logger.error(f"Error calculating portfolio stats: {str(e)}")
            raise
    
    async def get_strategy_performance(
        self,
        strategy_name: Optional[str] = None,
        timeframe: str = "all"
    ) -> Dict:
        """Analyze performance by trading strategy"""
        try:
            # Build base query
            query = select(TradingSession)
            
            if strategy_name:
                query = query.where(TradingSession.strategy_name == strategy_name)
            
            # Apply timeframe filter
            if timeframe != "all":
                days = self._timeframe_to_days(timeframe)
                cutoff = datetime.utcnow() - timedelta(days=days)
                query = query.where(TradingSession.start_time >= cutoff)
            
            # Execute query
            result = await self.session.execute(query)
            sessions = result.scalars().all()
            
            if not sessions:
                return {}
            
            # Group sessions by strategy
            strategies = {}
            for session in sessions:
                if session.strategy_name not in strategies:
                    strategies[session.strategy_name] = []
                strategies[session.strategy_name].append(session)
            
            # Calculate metrics for each strategy
            performance = {}
            for strat_name, strat_sessions in strategies.items():
                metrics = await self._calculate_strategy_metrics(strat_sessions)
                performance[strat_name] = metrics
            
            return performance
            
        except Exception as e:
            logger.error(f"Error analyzing strategy performance: {str(e)}")
            raise
    
    async def get_pair_performance(
        self,
        token_address: str,
        chain: str,
        timeframe: str = "all"
    ) -> Dict:
        """Analyze performance for a specific trading pair"""
        try:
            # Build query
            query = select(TradingSession).where(
                and_(
                    TradingSession.token_address == token_address,
                    TradingSession.chain == chain
                )
            )
            
            # Apply timeframe filter
            if timeframe != "all":
                days = self._timeframe_to_days(timeframe)
                cutoff = datetime.utcnow() - timedelta(days=days)
                query = query.where(TradingSession.start_time >= cutoff)
            
            # Execute query
            result = await self.session.execute(query)
            sessions = result.scalars().all()
            
            if not sessions:
                return {}
            
            # Get all trades for these sessions
            trade_query = select(TradeLog).where(
                TradeLog.session_id.in_([s.id for s in sessions])
            )
            trade_result = await self.session.execute(trade_query)
            trades = trade_result.scalars().all()
            
            # Calculate entry/exit timing performance
            timing_metrics = self._analyze_timing_performance(trades)
            
            # Calculate slippage metrics
            slippage_metrics = self._analyze_slippage(trades)
            
            # Calculate profit metrics
            profit_metrics = await self._calculate_profit_metrics(sessions)
            
            return {
                'overview': {
                    'total_sessions': len(sessions),
                    'total_trades': len(trades),
                    'total_volume': str(sum(t.total_value_usd for t in trades))
                },
                'timing': timing_metrics,
                'slippage': slippage_metrics,
                'profit': profit_metrics
            }
            
        except Exception as e:
            logger.error(f"Error analyzing pair performance: {str(e)}")
            raise
    
    async def generate_performance_report(
        self,
        wallet_address: str,
        timeframe: str = "all",
        include_trades: bool = False
    ) -> Dict:
        """Generate comprehensive performance report"""
        try:
            # Get portfolio stats
            portfolio = await self.get_portfolio_stats(wallet_address, timeframe)
            
            # Get strategy performance
            strategies = await self.get_strategy_performance(None, timeframe)
            
            # Get session details
            sessions_query = select(TradingSession).where(
                TradingSession.wallet_address == wallet_address
            )
            
            if timeframe != "all":
                days = self._timeframe_to_days(timeframe)
                cutoff = datetime.utcnow() - timedelta(days=days)
                sessions_query = sessions_query.where(
                    TradingSession.start_time >= cutoff
                )
            
            sessions_result = await self.session.execute(sessions_query)
            sessions = sessions_result.scalars().all()
            
            report = {
                'portfolio': portfolio,
                'strategies': strategies,
                'sessions': [
                    {
                        'id': s.id,
                        'token_address': s.token_address,
                        'chain': s.chain,
                        'strategy': s.strategy_name,
                        'start_time': s.start_time.isoformat(),
                        'end_time': s.end_time.isoformat() if s.end_time else None,
                        'initial_investment': str(s.initial_investment),
                        'final_value': str(s.final_value) if s.final_value else None,
                        'roi': float(s.roi_percentage) if s.roi_percentage else None,
                        'risk_score': float(s.risk_score),
                        'is_active': s.is_active
                    }
                    for s in sessions
                ]
            }
            
            if include_trades:
                # Get detailed trade history
                trades_query = select(TradeLog).where(
                    TradeLog.session_id.in_([s.id for s in sessions])
                ).order_by(TradeLog.timestamp.desc())
                
                trades_result = await self.session.execute(trades_query)
                trades = trades_result.scalars().all()
                
                report['trades'] = [t.to_dict() for t in trades]
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating performance report: {str(e)}")
            raise
    
    def _timeframe_to_days(self, timeframe: str) -> int:
        """Convert timeframe string to number of days"""
        timeframes = {
            "24h": 1,
            "7d": 7,
            "30d": 30,
            "90d": 90,
            "180d": 180,
            "1y": 365
        }
        return timeframes.get(timeframe, 0)
    
    def _empty_portfolio_stats(self) -> Dict:
        """Return empty portfolio stats structure"""
        return {
            'overview': {
                'total_sessions': 0,
                'total_trades': 0,
                'active_sessions': 0,
                'total_investment': "0",
                'total_final_value': "0",
                'total_profit_loss': "0"
            },
            'performance': {
                'win_rate': 0.0,
                'average_roi': 0.0,
                'roi_volatility': 0.0,
                'best_roi': 0.0,
                'worst_roi': 0.0
            },
            'risk_metrics': {
                'average_risk_score': 0.0,
                'high_risk_exposure': 0.0,
                'risk_adjusted_return': 0.0
            },
            'trade_metrics': {
                'average_trade_size': "0",
                'average_slippage': 0.0,
                'execution_success_rate': 0.0
            }
        }
    
    async def _calculate_risk_metrics(
        self,
        sessions: List[TradingSession]
    ) -> Dict:
        """Calculate risk-related metrics"""
        if not sessions:
            return {
                'average_risk_score': 0.0,
                'high_risk_exposure': 0.0,
                'risk_adjusted_return': 0.0
            }
        
        risk_scores = [float(s.risk_score) for s in sessions]
        avg_risk = statistics.mean(risk_scores)
        
        # Calculate high risk exposure (% of investment in high risk trades)
        high_risk_investment = sum(
            s.initial_investment
            for s in sessions
            if float(s.risk_score) >= 0.7
        )
        total_investment = sum(s.initial_investment for s in sessions)
        high_risk_exposure = (
            float(high_risk_investment / total_investment * 100)
            if total_investment > 0 else 0
        )
        
        # Calculate risk-adjusted return (ROI / Risk Score)
        risk_adjusted_returns = [
            float(s.roi_percentage / s.risk_score)
            for s in sessions
            if s.roi_percentage is not None and float(s.risk_score) > 0
        ]
        avg_risk_adjusted_return = (
            statistics.mean(risk_adjusted_returns)
            if risk_adjusted_returns else 0
        )
        
        return {
            'average_risk_score': avg_risk,
            'high_risk_exposure': high_risk_exposure,
            'risk_adjusted_return': avg_risk_adjusted_return
        }
    
    def _calculate_trade_metrics(self, trades: List[TradeLog]) -> Dict:
        """Calculate trade execution metrics"""
        if not trades:
            return {
                'average_trade_size': "0",
                'average_slippage': 0.0,
                'execution_success_rate': 0.0
            }
        
        # Calculate average trade size
        trade_sizes = [t.total_value_usd for t in trades]
        avg_size = sum(trade_sizes) / len(trades)
        
        # Calculate average slippage
        slippages = [
            float(t.slippage_percentage)
            for t in trades
            if t.slippage_percentage is not None
        ]
        avg_slippage = statistics.mean(slippages) if slippages else 0
        
        # Calculate execution success rate
        success_rate = (
            sum(1 for t in trades if t.status == TradeStatus.EXECUTED) /
            len(trades) * 100
        )
        
        return {
            'average_trade_size': str(avg_size),
            'average_slippage': avg_slippage,
            'execution_success_rate': success_rate
        }
    
    async def _calculate_strategy_metrics(
        self,
        sessions: List[TradingSession]
    ) -> Dict:
        """Calculate performance metrics for a strategy"""
        if not sessions:
            return {}
        
        # Calculate basic metrics
        total_investment = sum(s.initial_investment for s in sessions)
        total_final = sum(s.final_value for s in sessions if s.final_value)
        total_profit = total_final - total_investment if total_final else Decimal('0')
        
        # Calculate ROI stats
        rois = [
            float(s.roi_percentage)
            for s in sessions
            if s.roi_percentage is not None
        ]
        
        avg_roi = statistics.mean(rois) if rois else 0
        roi_std = statistics.stdev(rois) if len(rois) > 1 else 0
        
        # Calculate win rate
        profitable = sum(1 for roi in rois if roi > 0)
        win_rate = (profitable / len(rois) * 100) if rois else 0
        
        # Get risk metrics
        risk_metrics = await self._calculate_risk_metrics(sessions)
        
        return {
            'total_sessions': len(sessions),
            'total_investment': str(total_investment),
            'total_profit': str(total_profit),
            'average_roi': avg_roi,
            'roi_volatility': roi_std,
            'win_rate': win_rate,
            'risk_metrics': risk_metrics
        }
    
    def _analyze_timing_performance(self, trades: List[TradeLog]) -> Dict:
        """Analyze entry/exit timing performance"""
        if not trades:
            return {}
        
        # Group trades by session
        sessions = {}
        for trade in trades:
            if trade.session_id not in sessions:
                sessions[trade.session_id] = []
            sessions[trade.session_id].append(trade)
        
        # Analyze timing for each session
        timing_scores = []
        for session_trades in sessions.values():
            entry_trades = [
                t for t in session_trades
                if t.trade_type == TradeType.ENTRY
            ]
            exit_trades = [
                t for t in session_trades
                if t.trade_type in [TradeType.EXIT, TradeType.TAKE_PROFIT]
            ]
            
            for entry in entry_trades:
                for exit in exit_trades:
                    if exit.timestamp > entry.timestamp:
                        # Calculate timing score based on profit
                        entry_value = float(entry.price_usd)
                        exit_value = float(exit.price_usd)
                        if entry_value > 0:
                            timing_score = (exit_value - entry_value) / entry_value
                            timing_scores.append(timing_score)
        
        if not timing_scores:
            return {
                'average_timing_score': 0.0,
                'best_timing_score': 0.0,
                'worst_timing_score': 0.0
            }
        
        return {
            'average_timing_score': statistics.mean(timing_scores),
            'best_timing_score': max(timing_scores),
            'worst_timing_score': min(timing_scores)
        }
    
    def _analyze_slippage(self, trades: List[TradeLog]) -> Dict:
        """Analyze slippage patterns"""
        if not trades:
            return {}
        
        # Collect slippage data
        entry_slippage = [
            float(t.slippage_percentage)
            for t in trades
            if t.trade_type == TradeType.ENTRY and t.slippage_percentage
        ]
        
        exit_slippage = [
            float(t.slippage_percentage)
            for t in trades
            if t.trade_type in [TradeType.EXIT, TradeType.TAKE_PROFIT]
            and t.slippage_percentage
        ]
        
        return {
            'entry_slippage': {
                'average': statistics.mean(entry_slippage) if entry_slippage else 0,
                'max': max(entry_slippage) if entry_slippage else 0
            },
            'exit_slippage': {
                'average': statistics.mean(exit_slippage) if exit_slippage else 0,
                'max': max(exit_slippage) if exit_slippage else 0
            }
        }
    
    async def _calculate_profit_metrics(
        self,
        sessions: List[TradingSession]
    ) -> Dict:
        """Calculate detailed profit metrics"""
        if not sessions:
            return {}
        
        # Calculate profit metrics
        rois = [
            float(s.roi_percentage)
            for s in sessions
            if s.roi_percentage is not None
        ]
        
        profitable_sessions = sum(1 for roi in rois if roi > 0)
        
        return {
            'total_sessions': len(sessions),
            'profitable_sessions': profitable_sessions,
            'average_roi': statistics.mean(rois) if rois else 0,
            'best_roi': max(rois) if rois else 0,
            'worst_roi': min(rois) if rois else 0,
            'roi_volatility': statistics.stdev(rois) if len(rois) > 1 else 0
        }
