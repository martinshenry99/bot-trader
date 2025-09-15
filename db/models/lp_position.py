from datetime import datetime
from typing import Dict, Optional
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.base import Base

class LPPosition(Base):
    """Model for tracking liquidity pool positions"""
    
    __tablename__ = 'lp_positions'
    
    id = Column(Integer, primary_key=True)
    wallet_address = Column(String, nullable=False)
    pool_address = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    token0_symbol = Column(String, nullable=False)
    token1_symbol = Column(String, nullable=False)
    position_size = Column(Float, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow)
    last_metrics = Column(JSON, nullable=True)
    historical_metrics = Column(JSON, nullable=True)
    
    async def update_metrics(self, metrics: Dict):
        """Update position metrics with new data"""
        if self.last_metrics:
            if not self.historical_metrics:
                self.historical_metrics = []
            self.historical_metrics.append(self.last_metrics)
            
        self.last_metrics = metrics
        self.last_updated = datetime.utcnow()
    
    @classmethod
    async def get_active_positions(cls, session: AsyncSession, wallet_address: Optional[str] = None):
        """Get all active LP positions, optionally filtered by wallet"""
        query = session.query(cls)
        if wallet_address:
            query = query.filter(cls.wallet_address == wallet_address)
        return await query.all()
    
    def __repr__(self):
        return f"<LPPosition {self.token0_symbol}-{self.token1_symbol} pool={self.pool_address}>"
