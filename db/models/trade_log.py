"""Database models for trade logging system"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional
from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime, 
    JSON, Boolean, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
import enum
from db.models.base import Base

class TradeType(enum.Enum):
    ENTRY = "entry"
    EXIT = "exit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"

class TradeStatus(enum.Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TradingSession(Base):
    """Represents a complete trading session for a token"""
    __tablename__ = 'trading_sessions'
    
    id = Column(Integer, primary_key=True)
    token_address = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    wallet_address = Column(String, nullable=False)
    
    # Session details
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Strategy info
    strategy_name = Column(String, nullable=False)
    strategy_config = Column(JSON, nullable=True)
    
    # Performance metrics
    initial_investment = Column(Numeric(precision=28, scale=18))
    final_value = Column(Numeric(precision=28, scale=18), nullable=True)
    profit_loss = Column(Numeric(precision=28, scale=18), nullable=True)
    roi_percentage = Column(Numeric(precision=10, scale=2), nullable=True)
    
    # Risk metrics snapshot
    risk_score = Column(Numeric(precision=5, scale=2))
    risk_factors = Column(JSON)
    
    # Relationships
    trades = relationship("TradeLog", back_populates="session")
    
    async def calculate_performance(self):
        """Calculate session performance metrics"""
        if not self.end_time:
            return
            
        if self.initial_investment and self.final_value:
            self.profit_loss = self.final_value - self.initial_investment
            if self.initial_investment > 0:
                self.roi_percentage = (
                    (self.final_value - self.initial_investment) / 
                    self.initial_investment * 100
                )

class TradeLog(Base):
    """Detailed log of individual trades"""
    __tablename__ = 'trade_logs'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('trading_sessions.id'))
    
    # Trade details
    timestamp = Column(DateTime, default=datetime.utcnow)
    trade_type = Column(Enum(TradeType))
    status = Column(Enum(TradeStatus), default=TradeStatus.PENDING)
    
    # Token details
    token_address = Column(String, nullable=False)
    token_symbol = Column(String)
    chain = Column(String, nullable=False)
    
    # Transaction details
    amount = Column(Numeric(precision=28, scale=18))
    price_usd = Column(Numeric(precision=28, scale=18))
    total_value_usd = Column(Numeric(precision=28, scale=18))
    gas_used = Column(Numeric(precision=28, scale=18), nullable=True)
    gas_price = Column(Numeric(precision=28, scale=18), nullable=True)
    transaction_hash = Column(String, nullable=True)
    
    # Market conditions
    market_data = Column(JSON, nullable=True)
    technical_indicators = Column(JSON, nullable=True)
    
    # Decision factors
    entry_reasons = Column(JSON, nullable=True)
    exit_reasons = Column(JSON, nullable=True)
    risk_assessment = Column(JSON, nullable=True)
    
    # Slippage and execution
    expected_price = Column(Numeric(precision=28, scale=18))
    actual_price = Column(Numeric(precision=28, scale=18), nullable=True)
    slippage_percentage = Column(Numeric(precision=10, scale=2), nullable=True)
    execution_time = Column(Numeric(precision=10, scale=2), nullable=True)  # milliseconds
    
    # Relationships
    session = relationship("TradingSession", back_populates="trades")
    
    def calculate_slippage(self):
        """Calculate price slippage percentage"""
        if self.expected_price and self.actual_price and self.expected_price > 0:
            self.slippage_percentage = abs(
                (self.actual_price - self.expected_price) / 
                self.expected_price * 100
            )
    
    def to_dict(self) -> Dict:
        """Convert trade log to dictionary format"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'trade_type': self.trade_type.value,
            'status': self.status.value,
            'token_address': self.token_address,
            'token_symbol': self.token_symbol,
            'chain': self.chain,
            'amount': str(self.amount),
            'price_usd': str(self.price_usd),
            'total_value_usd': str(self.total_value_usd),
            'transaction_hash': self.transaction_hash,
            'slippage_percentage': float(self.slippage_percentage) if self.slippage_percentage else None,
            'execution_time': float(self.execution_time) if self.execution_time else None,
            'entry_reasons': self.entry_reasons,
            'exit_reasons': self.exit_reasons,
            'risk_assessment': self.risk_assessment
        }
