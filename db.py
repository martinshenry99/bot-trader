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
    wallet_watches = relationship("WalletWatch", back_populates="user")
    alert_config = relationship("AlertConfig", back_populates="user", uselist=False)
    blacklist_entries = relationship("BlacklistEntry", back_populates="user")

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

class WalletWatch(Base):
    __tablename__ = 'wallet_watches'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    wallet_address = Column(String, nullable=False)
    wallet_name = Column(String)  # User-defined name for the wallet
    chains = Column(String)  # Comma-separated list of chains to monitor
    is_active = Column(Boolean, default=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    # Performance tracking
    total_pnl = Column(Float)
    win_rate = Column(Float)
    total_trades = Column(Integer)
    best_multiplier = Column(Float)
    last_active = Column(DateTime)
    reputation_score = Column(Float)

    # Relationships
    user = relationship("User", back_populates="wallet_watches")

class AlertConfig(Base):
    __tablename__ = 'alert_configs'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Alert settings
    min_trade_size_usd = Column(Float, default=100.0)
    max_alerts_per_hour = Column(Integer, default=20)
    monitored_chains = Column(String)  # Comma-separated: ethereum,bsc,solana

    # Alert types
    buy_alerts_enabled = Column(Boolean, default=True)
    sell_alerts_enabled = Column(Boolean, default=True)
    moonshot_alerts_enabled = Column(Boolean, default=True)

    # Filters
    blacklisted_wallets = Column(Text)  # Comma-separated wallet addresses
    blacklisted_tokens = Column(Text)   # Comma-separated token addresses

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="alert_config")

class BlacklistEntry(Base):
    __tablename__ = 'blacklist_entries'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    entry_type = Column(String, nullable=False)  # 'wallet' or 'token'
    address = Column(String, nullable=False)
    reason = Column(String)
    added_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="blacklist_entries")

class MoonshotWallet(Base):
    __tablename__ = 'moonshot_wallets'

    id = Column(Integer, primary_key=True)
    wallet_address = Column(String, unique=True, nullable=False)
    best_multiplier = Column(Float, nullable=False)
    total_pnl_usd = Column(Float)
    win_rate = Column(Float)
    total_trades = Column(Integer)
    best_trade_token = Column(String)
    best_trade_amount = Column(Float)
    chains = Column(String)
    reputation_score = Column(Float)
    last_updated = Column(DateTime, default=datetime.utcnow)

    # Performance over time
    multiplier_30d = Column(Float)
    multiplier_7d = Column(Float)
    multiplier_24h = Column(Float)

class DailyReport(Base):
    __tablename__ = 'daily_reports'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    report_date = Column(DateTime, nullable=False)

    # Trading metrics
    total_trades = Column(Integer, default=0)
    successful_trades = Column(Integer, default=0)
    failed_trades = Column(Integer, default=0)
    total_pnl_usd = Column(Float, default=0.0)

    # Alert metrics
    alerts_received = Column(Integer, default=0)
    alerts_acted_on = Column(Integer, default=0)

    # Portfolio metrics
    portfolio_value_usd = Column(Float)
    portfolio_change_pct = Column(Float)

    # Top performers
    best_trade_pnl = Column(Float)
    worst_trade_pnl = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)

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

class ExecutorWallet(Base):
    __tablename__ = 'executor_wallets'

    id = Column(Integer, primary_key=True)
    address = Column(String, nullable=False, unique=True)
    keystore_path = Column(String, nullable=False)
    chain = Column(String, default='ethereum')
    label = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime)

    # Wallet metrics
    total_transactions = Column(Integer, default=0)
    total_volume_usd = Column(Float, default=0.0)
    success_rate = Column(Float, default=0.0)


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