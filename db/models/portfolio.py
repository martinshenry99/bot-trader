"""
Database models for portfolio tracking
"""

from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column, Integer, String, Float, DateTime,
    ForeignKey, JSON, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserWallet(Base):
    """User wallet addresses for different chains"""
    
    __tablename__ = 'user_wallets'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    chain = Column(String(20), nullable=False)
    address = Column(String(66), nullable=False)
    label = Column(String(100))
    created_at = Column(DateTime, nullable=False)
    last_balance_check = Column(DateTime)
    
    @classmethod
    async def get_by_user(
        cls,
        user_id: int
    ) -> List['UserWallet']:
        """Get user's wallet addresses"""
        return [wallet for wallet in cls.query.filter_by(user_id=user_id)]
        
    @classmethod
    async def create(
        cls,
        user_id: int,
        chain: str,
        address: str,
        label: Optional[str] = None
    ) -> 'UserWallet':
        """Create new user wallet"""
        wallet = cls(
            user_id=user_id,
            chain=chain,
            address=address,
            label=label,
            created_at=datetime.now()
        )
        # Add to session and commit
        return wallet

class TokenBalance(Base):
    """Token balance tracking"""
    
    __tablename__ = 'token_balances'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    chain = Column(String(20), nullable=False)
    token_address = Column(String(66), nullable=False)
    amount = Column(String)  # Decimal as string
    price_usd = Column(Float)
    last_updated = Column(DateTime, nullable=False)
    metadata = Column(JSON)  # Additional token info
    
    @property
    def amount_decimal(self) -> Decimal:
        """Get amount as Decimal"""
        return Decimal(self.amount)
        
    @classmethod
    async def get_by_user(
        cls,
        user_id: int,
        chain: Optional[str] = None
    ) -> List['TokenBalance']:
        """Get user's token balances"""
        if chain:
            return [
                balance for balance in cls.query.filter_by(
                    user_id=user_id,
                    chain=chain
                )
            ]
        return [
            balance for balance in cls.query.filter_by(
                user_id=user_id
            )
        ]
        
    @classmethod
    async def update_balance(
        cls,
        user_id: int,
        chain: str,
        token_address: str,
        amount: Decimal,
        price_usd: float,
        metadata: Optional[Dict] = None
    ) -> 'TokenBalance':
        """Update token balance"""
        balance = cls.query.filter_by(
            user_id=user_id,
            chain=chain,
            token_address=token_address
        ).first()
        
        if balance:
            balance.amount = str(amount)
            balance.price_usd = price_usd
            balance.last_updated = datetime.now()
            if metadata:
                balance.metadata = metadata
        else:
            balance = cls(
                user_id=user_id,
                chain=chain,
                token_address=token_address,
                amount=str(amount),
                price_usd=price_usd,
                last_updated=datetime.now(),
                metadata=metadata
            )
            
        # Add to session and commit
        return balance

class PortfolioSnapshot(Base):
    """Historical portfolio snapshots"""
    
    __tablename__ = 'portfolio_snapshots'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    total_value_usd = Column(Float, nullable=False)
    chain_values = Column(JSON)  # Chain-wise values
    positions = Column(JSON)  # Token positions
    metadata = Column(JSON)  # Additional metrics
    
    @classmethod
    async def create_snapshot(
        cls,
        user_id: int,
        portfolio: Dict
    ) -> 'PortfolioSnapshot':
        """Create portfolio snapshot"""
        snapshot = cls(
            user_id=user_id,
            timestamp=datetime.now(),
            total_value_usd=float(portfolio['total_value_usd']),
            chain_values=portfolio['chains'],
            positions=portfolio['top_positions'],
            metadata={
                'performance': portfolio['performance'],
                'risk_metrics': portfolio['risk_metrics']
            }
        )
        # Add to session and commit
        return snapshot
        
    @classmethod
    async def get_history(
        cls,
        user_id: int,
        days: int = 30
    ) -> List['PortfolioSnapshot']:
        """Get historical snapshots"""
        cutoff = datetime.now() - timedelta(days=days)
        return [
            snapshot for snapshot in cls.query.filter(
                cls.user_id == user_id,
                cls.timestamp >= cutoff
            ).order_by(cls.timestamp.desc())
        ]

class PortfolioAlert(Base):
    """Portfolio alerts configuration"""
    
    __tablename__ = 'portfolio_alerts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    alert_type = Column(String(50), nullable=False)
    threshold = Column(Float, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False)
    last_triggered = Column(DateTime)
    
    @classmethod
    async def create_alert(
        cls,
        user_id: int,
        alert_type: str,
        threshold: float,
        description: str
    ) -> 'PortfolioAlert':
        """Create new portfolio alert"""
        alert = cls(
            user_id=user_id,
            alert_type=alert_type,
            threshold=threshold,
            description=description,
            created_at=datetime.now()
        )
        # Add to session and commit
        return alert
