"""
Database models for strategy management
"""

from typing import Dict, Optional
import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, Text, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserStrategy(Base):
    """User strategy configuration and state"""
    
    __tablename__ = 'user_strategies'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    strategy_name = Column(String(50), nullable=False)
    config = Column(Text, nullable=False)  # JSON string
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    last_run = Column(DateTime)
    
    # Performance metrics
    total_trades = Column(Integer, default=0)
    successful_trades = Column(Integer, default=0)
    total_profit_usd = Column(Float, default=0.0)
    max_drawdown = Column(Float)
    win_rate = Column(Float)
    
    def get_config(self) -> Dict:
        """Get parsed configuration"""
        return json.loads(self.config)
        
    def update_config(self, config: Dict) -> None:
        """Update strategy configuration"""
        self.config = json.dumps(config)
        self.updated_at = datetime.now()
        
    @classmethod
    async def create(
        cls,
        user_id: int,
        strategy_name: str,
        config: str,
        created_at: datetime
    ) -> 'UserStrategy':
        """Create new user strategy"""
        strategy = cls(
            user_id=user_id,
            strategy_name=strategy_name,
            config=config,
            created_at=created_at,
            updated_at=created_at
        )
        # Add to session and commit
        return strategy
        
    @classmethod
    async def get_by_user(
        cls,
        user_id: int,
        strategy_name: Optional[str] = None
    ) -> list['UserStrategy']:
        """Get user's strategies"""
        # Query strategies
        if strategy_name:
            return [strategy for strategy in cls.query.filter_by(
                user_id=user_id,
                strategy_name=strategy_name
            )]
        return [strategy for strategy in cls.query.filter_by(
            user_id=user_id
        )]

class StrategyTrade(Base):
    """Individual strategy trade record"""
    
    __tablename__ = 'strategy_trades'
    
    id = Column(Integer, primary_key=True)
    strategy_id = Column(
        Integer,
        ForeignKey('user_strategies.id'),
        nullable=False
    )
    chain = Column(String(10), nullable=False)
    token_address = Column(String(66), nullable=False)
    trade_type = Column(String(4), nullable=False)  # BUY/SELL
    amount = Column(String)  # Decimal as string
    price_usd = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    tx_hash = Column(String(66))
    status = Column(String(20), nullable=False)
    profit_loss = Column(Float)
    
    strategy = relationship("UserStrategy", backref="trades")
    
    @property
    def amount_decimal(self) -> Decimal:
        """Get amount as Decimal"""
        return Decimal(self.amount)
        
    @classmethod
    async def create(
        cls,
        strategy_id: int,
        chain: str,
        token_address: str,
        trade_type: str,
        amount: Decimal,
        price_usd: float,
        timestamp: datetime,
        tx_hash: Optional[str] = None
    ) -> 'StrategyTrade':
        """Create new strategy trade"""
        trade = cls(
            strategy_id=strategy_id,
            chain=chain,
            token_address=token_address,
            trade_type=trade_type,
            amount=str(amount),
            price_usd=price_usd,
            timestamp=timestamp,
            tx_hash=tx_hash,
            status='PENDING'
        )
        # Add to session and commit
        return trade
        
    async def update_status(
        self,
        status: str,
        profit_loss: Optional[float] = None
    ) -> None:
        """Update trade status and P&L"""
        self.status = status
        if profit_loss is not None:
            self.profit_loss = profit_loss
            
        if status == 'COMPLETED' and self.strategy:
            # Update strategy metrics
            self.strategy.total_trades += 1
            if profit_loss and profit_loss > 0:
                self.strategy.successful_trades += 1
                self.strategy.total_profit_usd += profit_loss
                
            # Update win rate
            if self.strategy.total_trades > 0:
                self.strategy.win_rate = (
                    self.strategy.successful_trades /
                    self.strategy.total_trades
                )
                
class StrategyAlert(Base):
    """Strategy-related alerts and notifications"""
    
    __tablename__ = 'strategy_alerts'
    
    id = Column(Integer, primary_key=True)
    strategy_id = Column(
        Integer,
        ForeignKey('user_strategies.id'),
        nullable=False
    )
    alert_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    metadata = Column(JSON)
    created_at = Column(DateTime, nullable=False)
    acknowledged = Column(Boolean, default=False)
    
    strategy = relationship("UserStrategy", backref="alerts")
    
    @classmethod
    async def create(
        cls,
        strategy_id: int,
        alert_type: str,
        message: str,
        metadata: Optional[Dict] = None
    ) -> 'StrategyAlert':
        """Create new strategy alert"""
        alert = cls(
            strategy_id=strategy_id,
            alert_type=alert_type,
            message=message,
            metadata=metadata,
            created_at=datetime.now()
        )
        # Add to session and commit
        return alert
        
    async def acknowledge(self) -> None:
        """Mark alert as acknowledged"""
        self.acknowledged = True
