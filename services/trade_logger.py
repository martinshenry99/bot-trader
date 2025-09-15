"""Service for managing trade logging and analysis"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from db.models.trade_log import (
    TradingSession, TradeLog, 
    TradeType, TradeStatus
)
from services.risk_scorer import RiskScorer

logger = logging.getLogger(__name__)

class TradeLogger:
    """Handles trade logging and session management"""
    
    def __init__(self, session: AsyncSession, risk_scorer: RiskScorer):
        self.session = session
        self.risk_scorer = risk_scorer
    
    async def start_session(
        self,
        token_address: str,
        chain: str,
        wallet_address: str,
        strategy_name: str,
        initial_investment: Decimal,
        strategy_config: Optional[Dict] = None
    ) -> TradingSession:
        """Start a new trading session"""
        try:
            # Get risk assessment
            risk_metrics = await self.risk_scorer.calculate_risk_score(
                token_address=token_address,
                chain=chain
            )
            
            # Create session
            session = TradingSession(
                token_address=token_address,
                chain=chain,
                wallet_address=wallet_address,
                strategy_name=strategy_name,
                strategy_config=strategy_config,
                initial_investment=initial_investment,
                risk_score=Decimal(str(risk_metrics.overall_risk)),
                risk_factors=risk_metrics.risk_factors
            )
            
            self.session.add(session)
            await self.session.commit()
            
            logger.info(
                f"Started trading session {session.id} for {token_address} "
                f"on {chain} using {strategy_name}"
            )
            
            return session
            
        except Exception as e:
            logger.error(f"Error starting trading session: {str(e)}")
            await self.session.rollback()
            raise
    
    async def log_trade(
        self,
        session_id: int,
        trade_type: TradeType,
        token_address: str,
        token_symbol: str,
        chain: str,
        amount: Decimal,
        price_usd: Decimal,
        expected_price: Decimal,
        entry_reasons: Optional[List[str]] = None,
        exit_reasons: Optional[List[str]] = None,
        market_data: Optional[Dict] = None,
        technical_indicators: Optional[Dict] = None
    ) -> TradeLog:
        """Log a trade execution"""
        try:
            trade = TradeLog(
                session_id=session_id,
                trade_type=trade_type,
                token_address=token_address,
                token_symbol=token_symbol,
                chain=chain,
                amount=amount,
                price_usd=price_usd,
                total_value_usd=amount * price_usd,
                expected_price=expected_price,
                entry_reasons=entry_reasons,
                exit_reasons=exit_reasons,
                market_data=market_data,
                technical_indicators=technical_indicators
            )
            
            self.session.add(trade)
            await self.session.commit()
            
            logger.info(
                f"Logged {trade_type.value} trade {trade.id} for {token_symbol}: "
                f"{amount} @ ${price_usd}"
            )
            
            return trade
            
        except Exception as e:
            logger.error(f"Error logging trade: {str(e)}")
            await self.session.rollback()
            raise
    
    async def update_trade_execution(
        self,
        trade_id: int,
        actual_price: Decimal,
        transaction_hash: str,
        gas_used: Decimal,
        gas_price: Decimal,
        execution_time: float,
        status: TradeStatus = TradeStatus.EXECUTED
    ):
        """Update trade with execution details"""
        try:
            trade = await self.session.get(TradeLog, trade_id)
            if not trade:
                raise ValueError(f"Trade {trade_id} not found")
                
            trade.actual_price = actual_price
            trade.transaction_hash = transaction_hash
            trade.gas_used = gas_used
            trade.gas_price = gas_price
            trade.execution_time = execution_time
            trade.status = status
            
            trade.calculate_slippage()
            
            await self.session.commit()
            
            logger.info(
                f"Updated trade {trade_id} execution details: "
                f"tx={transaction_hash}, status={status.value}"
            )
            
        except Exception as e:
            logger.error(f"Error updating trade execution: {str(e)}")
            await self.session.rollback()
            raise
    
    async def end_session(
        self,
        session_id: int,
        final_value: Decimal
    ):
        """End a trading session and calculate performance"""
        try:
            session = await self.session.get(TradingSession, session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")
                
            session.end_time = datetime.utcnow()
            session.is_active = False
            session.final_value = final_value
            
            await session.calculate_performance()
            await self.session.commit()
            
            logger.info(
                f"Ended session {session_id} with final value ${final_value} "
                f"(ROI: {session.roi_percentage}%)"
            )
            
        except Exception as e:
            logger.error(f"Error ending trading session: {str(e)}")
            await self.session.rollback()
            raise
    
    async def get_session_history(
        self,
        wallet_address: Optional[str] = None,
        token_address: Optional[str] = None,
        strategy_name: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """Get trading session history with filters"""
        try:
            query = select(TradingSession)
            
            # Apply filters
            filters = []
            if wallet_address:
                filters.append(TradingSession.wallet_address == wallet_address)
            if token_address:
                filters.append(TradingSession.token_address == token_address)
            if strategy_name:
                filters.append(TradingSession.strategy_name == strategy_name)
                
            if filters:
                query = query.where(and_(*filters))
                
            # Order by most recent first
            query = query.order_by(TradingSession.start_time.desc())
            
            if limit:
                query = query.limit(limit)
                
            result = await self.session.execute(query)
            sessions = result.scalars().all()
            
            return [
                {
                    'id': s.id,
                    'token_address': s.token_address,
                    'chain': s.chain,
                    'strategy_name': s.strategy_name,
                    'start_time': s.start_time.isoformat(),
                    'end_time': s.end_time.isoformat() if s.end_time else None,
                    'initial_investment': float(s.initial_investment),
                    'final_value': float(s.final_value) if s.final_value else None,
                    'roi_percentage': float(s.roi_percentage) if s.roi_percentage else None,
                    'risk_score': float(s.risk_score),
                    'num_trades': len(s.trades)
                }
                for s in sessions
            ]
            
        except Exception as e:
            logger.error(f"Error getting session history: {str(e)}")
            raise
    
    async def get_trade_details(self, session_id: int) -> List[Dict]:
        """Get detailed trade logs for a session"""
        try:
            query = select(TradeLog).where(
                TradeLog.session_id == session_id
            ).order_by(TradeLog.timestamp)
            
            result = await self.session.execute(query)
            trades = result.scalars().all()
            
            return [trade.to_dict() for trade in trades]
            
        except Exception as e:
            logger.error(f"Error getting trade details: {str(e)}")
            raise
