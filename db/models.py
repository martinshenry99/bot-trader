"""
Database Models for Meme Trader V4 Pro
Exact schema as specified in requirements
"""

import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path("meme_trader.db")

@dataclass
class WalletData:
    """Wallet data structure"""
    address: str
    chain: str
    last_scanned_block: int
    score: float
    win_rate: float
    max_mult: float
    avg_roi: float
    last_active: int

@dataclass
class TokenData:
    """Token data structure"""
    contract: str
    chain: str
    liquidity_usd: float
    locked: bool
    owner: str
    honeypot: bool
    last_checked: int

@dataclass
class TradeData:
    """Trade data structure"""
    wallet: str
    token: str
    chain: str
    tx_hash: str
    action: str
    amount: float
    usd_at_trade: float
    timestamp: int

@dataclass
class AlertData:
    """Alert data structure"""
    type: str
    payload: str
    sent_at: int

@dataclass
class ExecutorData:
    """Executor data structure"""
    address: str
    keystore_path: str
    created_at: int

class DatabaseManager:
    """Database manager for Meme Trader V4 Pro"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self.init_database()
    
    def init_database(self):
        """Initialize database with exact schema"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create tables with exact schema
                cursor.executescript("""
                    -- Watchlist table
                    CREATE TABLE IF NOT EXISTS watchlist (
                        address TEXT NOT NULL,
                        type TEXT CHECK(type IN ('wallet','token')) NOT NULL,
                        chain TEXT NOT NULL,
                        label TEXT,
                        added_by INTEGER NOT NULL,
                        added_at INTEGER NOT NULL,
                        active INTEGER DEFAULT 1,
                        PRIMARY KEY (address, chain)
                    );
                    
                    -- Wallets table with chain-specific scanning
                    CREATE TABLE IF NOT EXISTS wallets (
                        address TEXT NOT NULL,
                        chain TEXT NOT NULL,
                        last_scanned_block INTEGER DEFAULT 0,
                        score REAL DEFAULT 0,
                        win_rate REAL DEFAULT 0,
                        max_mult REAL DEFAULT 1,
                        avg_roi REAL DEFAULT 1,
                        last_active INTEGER DEFAULT 0,
                        PRIMARY KEY (address, chain)
                    );
                    
                    -- Tokens table
                    CREATE TABLE IF NOT EXISTS tokens (
                        contract TEXT NOT NULL,
                        chain TEXT NOT NULL,
                        liquidity_usd REAL DEFAULT 0,
                        locked BOOLEAN DEFAULT 0,
                        owner TEXT,
                        honeypot BOOLEAN DEFAULT 0,
                        last_checked INTEGER DEFAULT 0,
                        PRIMARY KEY (contract, chain)
                    );
                    
                    -- Trades table
                    CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        wallet TEXT NOT NULL,
                        token TEXT NOT NULL,
                        chain TEXT NOT NULL,
                        tx_hash TEXT NOT NULL,
                        action TEXT NOT NULL,
                        amount REAL NOT NULL,
                        usd_at_trade REAL NOT NULL,
                        timestamp INTEGER NOT NULL
                    );
                    
                    -- Alerts table
                    CREATE TABLE IF NOT EXISTS alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        type TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        sent_at INTEGER NOT NULL
                    );
                    
                    -- Executors table
                    CREATE TABLE IF NOT EXISTS executors (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        address TEXT NOT NULL,
                        keystore_path TEXT NOT NULL,
                        created_at INTEGER NOT NULL
                    );
                    
                    -- User settings table for per-user preferences
                    CREATE TABLE IF NOT EXISTS user_settings (
                        user_id INTEGER NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        PRIMARY KEY (user_id, key)
                    );
                    
                    -- Key usage ledger for rotation tracking
                    CREATE TABLE IF NOT EXISTS key_ledger (
                        service TEXT NOT NULL,
                        key_hash TEXT NOT NULL,
                        last_used INTEGER DEFAULT 0,
                        usage_count INTEGER DEFAULT 0,
                        cooldown_until INTEGER DEFAULT 0,
                        PRIMARY KEY (service, key_hash)
                    );
                    
                    -- Create indexes for performance
                    CREATE INDEX IF NOT EXISTS idx_watchlist_active ON watchlist(active);
                    CREATE INDEX IF NOT EXISTS idx_wallets_score ON wallets(score DESC);
                    CREATE INDEX IF NOT EXISTS idx_wallets_chain ON wallets(chain);
                    CREATE INDEX IF NOT EXISTS idx_trades_wallet ON trades(wallet, chain);
                    CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp DESC);
                    CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(type);
                    CREATE INDEX IF NOT EXISTS idx_key_ledger_service ON key_ledger(service);
                """)
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    def add_wallet_to_watchlist(self, address: str, chain: str, user_id: int, 
                               wallet_type: str = 'wallet', label: str = None) -> bool:
        """Add wallet to watchlist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO watchlist 
                    (address, type, chain, label, added_by, added_at, active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                """, (address, wallet_type, chain, label, user_id, int(datetime.now().timestamp())))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to add wallet to watchlist: {e}")
            return False
    
    def remove_from_watchlist(self, address: str, chain: str, user_id: int) -> bool:
        """Remove wallet from watchlist (deactivate)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE watchlist 
                    SET active = 0 
                    WHERE address = ? AND chain = ? AND added_by = ?
                """, (address, chain, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to remove from watchlist: {e}")
            return False
    
    def get_user_watchlist(self, user_id: int, active_only: bool = True) -> List[Dict]:
        """Get user's watchlist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = """
                    SELECT address, type, chain, label, added_at, active
                    FROM watchlist 
                    WHERE added_by = ?
                """
                params = [user_id]
                
                if active_only:
                    query += " AND active = 1"
                
                query += " ORDER BY added_at DESC"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get user watchlist: {e}")
            return []
    
    def update_wallet_metrics(self, address: str, chain: str, metrics: Dict) -> bool:
        """Update wallet metrics in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO wallets 
                    (address, chain, last_scanned_block, score, win_rate, max_mult, avg_roi, last_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    address, chain,
                    metrics.get('last_scanned_block', 0),
                    metrics.get('score', 0),
                    metrics.get('win_rate', 0),
                    metrics.get('max_mult', 1),
                    metrics.get('avg_roi', 1),
                    int(datetime.now().timestamp())
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to update wallet metrics: {e}")
            return False
    
    def get_wallet_metrics(self, address: str, chain: str) -> Optional[WalletData]:
        """Get wallet metrics from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT address, chain, last_scanned_block, score, win_rate, max_mult, avg_roi, last_active
                    FROM wallets 
                    WHERE address = ? AND chain = ?
                """, (address, chain))
                
                row = cursor.fetchone()
                if row:
                    return WalletData(*row)
                return None
        except Exception as e:
            logger.error(f"Failed to get wallet metrics: {e}")
            return None
    
    def add_trade(self, trade: TradeData) -> bool:
        """Add trade to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO trades (wallet, token, chain, tx_hash, action, amount, usd_at_trade, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.wallet, trade.token, trade.chain, trade.tx_hash,
                    trade.action, trade.amount, trade.usd_at_trade, trade.timestamp
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to add trade: {e}")
            return False
    
    def get_wallet_trades(self, address: str, chain: str, limit: int = 100) -> List[Dict]:
        """Get wallet trades from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT wallet, token, chain, tx_hash, action, amount, usd_at_trade, timestamp
                    FROM trades 
                    WHERE wallet = ? AND chain = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (address, chain, limit))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get wallet trades: {e}")
            return []
    
    def add_alert(self, alert_type: str, payload: str) -> bool:
        """Add alert to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO alerts (type, payload, sent_at)
                    VALUES (?, ?, ?)
                """, (alert_type, payload, int(datetime.now().timestamp())))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to add alert: {e}")
            return False
    
    def get_user_setting(self, user_id: int, key: str, default: str = None) -> str:
        """Get user setting with fallback to default"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT value FROM user_settings 
                    WHERE user_id = ? AND key = ?
                """, (user_id, key))
                
                row = cursor.fetchone()
                return row[0] if row else default
        except Exception as e:
            logger.error(f"Failed to get user setting: {e}")
            return default
    
    def set_user_setting(self, user_id: int, key: str, value: str) -> bool:
        """Set user setting"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO user_settings (user_id, key, value)
                    VALUES (?, ?, ?)
                """, (user_id, key, value))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to set user setting: {e}")
            return False
    
    def update_key_usage(self, service: str, key_hash: str, cooldown_until: int = 0) -> bool:
        """Update key usage in ledger"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO key_ledger 
                    (service, key_hash, last_used, usage_count, cooldown_until)
                    VALUES (?, ?, ?, COALESCE((SELECT usage_count + 1 FROM key_ledger WHERE service = ? AND key_hash = ?), 1), ?)
                """, (service, key_hash, int(datetime.now().timestamp()), service, key_hash, cooldown_until))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to update key usage: {e}")
            return False
    
    def get_available_keys(self, service: str) -> List[str]:
        """Get available (non-cooldown) keys for service"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT key_hash FROM key_ledger 
                    WHERE service = ? AND (cooldown_until = 0 OR cooldown_until < ?)
                    ORDER BY usage_count ASC, last_used ASC
                """, (service, int(datetime.now().timestamp())))
                
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get available keys: {e}")
            return []
    
    def get_wallet_metrics_by_score(self, min_score: float = 0, limit: int = 100) -> List[WalletData]:
        """Get wallet metrics filtered by minimum score"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT address, chain, last_scanned_block, score, win_rate, max_mult, avg_roi, last_active
                    FROM wallets 
                    WHERE score >= ?
                    ORDER BY score DESC, last_active DESC
                    LIMIT ?
                """, (min_score, limit))
                
                rows = cursor.fetchall()
                return [WalletData(*row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get wallet metrics by score: {e}")
            return []

# Global database instance
db_manager = DatabaseManager()

def get_db_manager() -> DatabaseManager:
    """Get database manager instance"""
    return db_manager

def create_tables():
    """Create database tables"""
    db_manager.init_database()

def get_db_session():
    """Get database connection (for compatibility)"""
    return sqlite3.connect(db_manager.db_path) 