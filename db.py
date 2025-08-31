from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid
from config import Config

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True, nullable=False)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    wallets = relationship("Wallet", back_populates="user")
    trades = relationship("Trade", back_populates="user")

class Wallet(Base):
    __tablename__ = 'wallets'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    address = Column(String, nullable=False)
    name = Column(String)
    private_key_encrypted = Column(Text)  # Encrypted private key
    is_monitoring = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="wallets")
    transactions = relationship("Transaction", back_populates="wallet")

class Token(Base):
    __tablename__ = 'tokens'
    
    id = Column(Integer, primary_key=True)
    address = Column(String, unique=True, nullable=False)
    symbol = Column(String)
    name = Column(String)
    decimals = Column(Integer)
    is_monitored = Column(Boolean, default=False)
    is_honeypot = Column(Boolean)
    liquidity_usd = Column(Float)
    price_usd = Column(Float)
    market_cap = Column(Float)
    volume_24h = Column(Float)
    ai_score = Column(Float)
    sentiment_score = Column(Float)
    last_analyzed = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Trade(Base):
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    trade_id = Column(String, default=lambda: str(uuid.uuid4()))
    wallet_address = Column(String, nullable=False)
    token_address = Column(String, nullable=False)
    trade_type = Column(String, nullable=False)  # 'buy' or 'sell'
    amount_in = Column(Float)
    amount_out = Column(Float)
    token_in_address = Column(String)
    token_out_address = Column(String)
    price_usd = Column(Float)
    gas_fee = Column(Float)
    slippage = Column(Float)
    tx_hash = Column(String)
    status = Column(String, default='pending')  # pending, confirmed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="trades")

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False)
    tx_hash = Column(String, unique=True, nullable=False)
    from_address = Column(String)
    to_address = Column(String)
    value = Column(Float)
    token_address = Column(String)
    token_symbol = Column(String)
    gas_used = Column(Integer)
    gas_price = Column(Float)
    block_number = Column(Integer)
    timestamp = Column(DateTime)
    transaction_type = Column(String)  # 'send', 'receive', 'swap', etc.
    is_analyzed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    wallet = relationship("Wallet", back_populates="transactions")

class MonitoringAlert(Base):
    __tablename__ = 'monitoring_alerts'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    alert_type = Column(String, nullable=False)  # 'price_change', 'new_transaction', 'honeypot_detected'
    title = Column(String)
    message = Column(Text)
    token_address = Column(String)
    wallet_address = Column(String)
    trigger_value = Column(Float)
    is_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime)

# Database Setup
engine = create_engine(Config.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_session():
    """Get database session for direct use"""
    return SessionLocal()