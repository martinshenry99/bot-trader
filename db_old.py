"""
Database models for Meme Trader V4 Pro
"""

import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import logging

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


# Create database URL
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///meme_trader.db')

# Create engine
engine = create_engine(DATABASE_URL)

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class Token(Base):
    """Token information and analysis"""
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, index=True)
    address = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=True)
    symbol = Column(String, nullable=True)
    decimals = Column(Integer, default=18)
    chain = Column(String, default='ethereum')
    is_monitored = Column(Boolean, default=False)
    
    # Price and market data
    price_usd = Column(Float, default=0.0)
    market_cap = Column(Float, default=0.0)
    liquidity_usd = Column(Float, default=0.0)
    volume_24h = Column(Float, default=0.0)
    
    # Analysis data
    risk_score = Column(Integer, default=50)
    is_honeypot = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    token_address = Column(String)
    token_symbol = Column(String)
    chain = Column(String)
    amount = Column(Float)
    purchase_price_usd = Column(Float)
    current_price_usd = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class Trade(Base):
    """Trade execution records"""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    token_address = Column(String, nullable=False)
    token_symbol = Column(String, nullable=True)
    chain = Column(String, default='ethereum')
    
    # Trade details
    trade_type = Column(String, nullable=False)  # 'buy' or 'sell'
    amount_usd = Column(Float, nullable=False)
    token_amount = Column(Float, nullable=False)
    price_usd = Column(Float, nullable=False)
    
    # Transaction details
    transaction_hash = Column(String, nullable=True)
    gas_used = Column(Integer, default=0)
    gas_price = Column(Integer, default=0)
    
    # Status
    status = Column(String, default='pending')  # pending, confirmed, failed
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)

class AlertConfig(Base):
    """User alert configuration"""
    __tablename__ = "alert_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    
    # Alert types
    price_alerts_enabled = Column(Boolean, default=True)
    wallet_alerts_enabled = Column(Boolean, default=True)
    trade_alerts_enabled = Column(Boolean, default=True)
    
    # Price alert settings
    price_change_threshold = Column(Float, default=10.0)  # Percentage
    min_price_usd = Column(Float, default=0.0)
    max_price_usd = Column(Float, default=0.0)
    
    # Wallet alert settings
    wallet_activity_threshold = Column(Float, default=1000.0)  # USD
    min_profit_multiplier = Column(Float, default=2.0)
    
    # Notification settings
    telegram_notifications = Column(Boolean, default=True)
    email_notifications = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class BlacklistEntry(Base):
    """Blacklisted addresses and tokens"""
    __tablename__ = "blacklist"

    id = Column(Integer, primary_key=True, index=True)
    address = Column(String, nullable=False, unique=True, index=True)
    entry_type = Column(String, nullable=False)  # 'wallet', 'token', 'contract'
    chain = Column(String, default='ethereum')
    
    # Reason for blacklisting
    reason = Column(Text, nullable=True)
    risk_level = Column(String, default='high')  # low, medium, high
    
    # Metadata
    reported_by = Column(String, nullable=True)
    evidence = Column(Text, nullable=True)  # JSON string
    
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

class WalletWatch(Base):
    """Wallet watchlist and top trader tracking"""
    __tablename__ = 'wallet_watch'

    id = Column(Integer, primary_key=True)
    wallet_address = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False)
    chain = Column(String, default='ethereum')
    timeframe = Column(String, default='7d')

    # Performance metrics
    profit_multiplier = Column(Float, default=1.0)
    total_profit_usd = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    total_volume_usd = Column(Float, default=0.0)
    trade_count = Column(Integer, default=0)
    avg_roi = Column(Float, default=1.0)

    # Activity tracking
    last_activity = Column(DateTime)
    last_scanned = Column(DateTime, default=datetime.utcnow)
    trades_last_30_days = Column(Integer, default=0)
    recent_roi_positive = Column(Boolean, default=False)

    # Risk and safety
    risk_score = Column(Integer, default=50)
    classification = Column(String, default='Unknown')
    honeypot_interactions = Column(Integer, default=0)
    is_dev_wallet = Column(Boolean, default=False)
    is_blacklisted = Column(Boolean, default=False)

    # Graph metrics
    network_centrality = Column(Float, default=0.0)
    connected_wallets = Column(Integer, default=0)
    is_copycat = Column(Boolean, default=False)

    # Metadata
    top_tokens = Column(Text)  # JSON string
    wallet_name = Column(String)
    discovery_date = Column(DateTime, default=datetime.utcnow)
    scanner_score = Column(Integer, default=0)

    # Indexes
    __table_args__ = (
        Index('idx_wallet_chain', 'wallet_address', 'chain'),
        Index('idx_user_wallets', 'user_id', 'wallet_address'),
        Index('idx_scanner_score', 'scanner_score'),
        Index('idx_last_activity', 'last_activity'),
    )

class ExecutorWallet(Base):
    """Executor wallet for automated trading"""
    __tablename__ = 'executor_wallets'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    wallet_address = Column(String, nullable=False, unique=True)
    chain = Column(String, default='ethereum')
    
    # Wallet details
    wallet_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Security
    keystore_path = Column(String, nullable=True)
    is_encrypted = Column(Boolean, default=True)
    
    # Trading limits
    max_trade_usd = Column(Float, default=100.0)
    daily_limit_usd = Column(Float, default=1000.0)
    
    # Performance tracking
    total_trades = Column(Integer, default=0)
    total_volume_usd = Column(Float, default=0.0)
    success_rate = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)

class TopTraderScan(Base):
    """Track top trader scan results"""
    __tablename__ = 'top_trader_scans'

    id = Column(Integer, primary_key=True)
    scan_timestamp = Column(DateTime, default=datetime.utcnow)
    chain = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)

    # Scan results
    wallets_found = Column(Integer, default=0)
    qualifying_wallets = Column(Integer, default=0)
    scan_duration_seconds = Column(Float, default=0.0)

    # Filter results
    performance_filtered = Column(Integer, default=0)
    activity_filtered = Column(Integer, default=0)
    safety_filtered = Column(Integer, default=0)

    # Metadata
    scan_criteria = Column(Text)  # JSON string
    top_scorer_address = Column(String)
    top_score = Column(Integer, default=0)


def get_db_session():
    """Get database session"""
    return SessionLocal()

def create_tables():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)

# Create tables on import
create_tables()

logger.info("Database initialized successfully")