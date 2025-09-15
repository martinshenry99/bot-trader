"""
Historical validation database for caching and analysis
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
import sqlite3
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass

@dataclass
class ValidationResult:
    """Container for validation results"""
    token_address: str
    chain: str
    timestamp: datetime
    liquidity_usd: str
    volume_24h: str
    holder_count: int
    is_honeypot: bool
    is_blacklisted: bool
    price_impact_bps: int
    owner_balance_pct: float
    contract_verified: bool
    validation_score: int
    extra_data: Dict[str, Any]
    is_valid: bool
    ttl: int = 300  # 5 minutes default

class ValidationDatabase:
    """Manages historical validation results"""
    
    def __init__(
        self,
        db_path: str = "meme_trader.db",
        min_ttl: int = 60,
        max_ttl: int = 3600
    ):
        self.db_path = db_path
        self.min_ttl = min_ttl
        self.max_ttl = max_ttl
        self._lock = asyncio.Lock()
        self._setup_database()
        
    def _setup_database(self):
        """Create database tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS validations (
                    token_address TEXT,
                    chain TEXT,
                    timestamp DATETIME,
                    liquidity_usd TEXT,
                    volume_24h TEXT,
                    holder_count INTEGER,
                    is_honeypot BOOLEAN,
                    is_blacklisted BOOLEAN,
                    price_impact_bps INTEGER,
                    owner_balance_pct REAL,
                    contract_verified BOOLEAN,
                    validation_score INTEGER,
                    extra_data TEXT,
                    is_valid BOOLEAN,
                    ttl INTEGER,
                    PRIMARY KEY (token_address, chain)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_validations_timestamp 
                ON validations(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_validations_chain 
                ON validations(chain)
            """)
            
    @asynccontextmanager
    async def _get_connection(self):
        """Get database connection with lock"""
        async with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                yield conn
            finally:
                conn.close()
                
    async def store_validation(
        self,
        result: ValidationResult
    ):
        """Store validation result"""
        async with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO validations (
                    token_address,
                    chain,
                    timestamp,
                    liquidity_usd,
                    volume_24h,
                    holder_count,
                    is_honeypot,
                    is_blacklisted,
                    price_impact_bps,
                    owner_balance_pct,
                    contract_verified,
                    validation_score,
                    extra_data,
                    is_valid,
                    ttl
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.token_address,
                result.chain,
                result.timestamp.isoformat(),
                result.liquidity_usd,
                result.volume_24h,
                result.holder_count,
                result.is_honeypot,
                result.is_blacklisted,
                result.price_impact_bps,
                result.owner_balance_pct,
                result.contract_verified,
                result.validation_score,
                json.dumps(result.extra_data),
                result.is_valid,
                result.ttl
            ))
            conn.commit()
            
    async def get_validation(
        self,
        token_address: str,
        chain: str
    ) -> Optional[ValidationResult]:
        """Get validation result if not expired"""
        async with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT *
                FROM validations
                WHERE token_address = ? 
                AND chain = ?
            """, (token_address, chain))
            
            row = cursor.fetchone()
            if not row:
                return None
                
            # Check if expired
            timestamp = datetime.fromisoformat(row[2])
            ttl = row[14]
            if datetime.utcnow() - timestamp > timedelta(seconds=ttl):
                return None
                
            return ValidationResult(
                token_address=row[0],
                chain=row[1],
                timestamp=timestamp,
                liquidity_usd=row[3],
                volume_24h=row[4],
                holder_count=row[5],
                is_honeypot=bool(row[6]),
                is_blacklisted=bool(row[7]),
                price_impact_bps=row[8],
                owner_balance_pct=row[9],
                contract_verified=bool(row[10]),
                validation_score=row[11],
                extra_data=json.loads(row[12]),
                is_valid=bool(row[13]),
                ttl=ttl
            )
            
    async def get_valid_tokens(
        self,
        chain: str,
        min_liquidity: Optional[str] = None,
        min_score: Optional[int] = None
    ) -> List[ValidationResult]:
        """Get all valid tokens matching criteria"""
        async with self._get_connection() as conn:
            query = """
                SELECT *
                FROM validations
                WHERE chain = ?
                AND is_valid = 1
            """
            params = [chain]
            
            if min_liquidity:
                query += " AND CAST(liquidity_usd AS DECIMAL) >= ?"
                params.append(min_liquidity)
                
            if min_score:
                query += " AND validation_score >= ?"
                params.append(min_score)
                
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            results = []
            now = datetime.utcnow()
            
            for row in rows:
                timestamp = datetime.fromisoformat(row[2])
                ttl = row[14]
                
                # Skip expired entries
                if now - timestamp > timedelta(seconds=ttl):
                    continue
                    
                results.append(ValidationResult(
                    token_address=row[0],
                    chain=row[1],
                    timestamp=timestamp,
                    liquidity_usd=row[3],
                    volume_24h=row[4],
                    holder_count=row[5],
                    is_honeypot=bool(row[6]),
                    is_blacklisted=bool(row[7]),
                    price_impact_bps=row[8],
                    owner_balance_pct=row[9],
                    contract_verified=bool(row[10]),
                    validation_score=row[11],
                    extra_data=json.loads(row[12]),
                    is_valid=bool(row[13]),
                    ttl=ttl
                ))
                
            return results
            
    async def cleanup_expired(self):
        """Remove expired validations"""
        async with self._get_connection() as conn:
            conn.execute("""
                DELETE FROM validations
                WHERE datetime(timestamp) < datetime('now', ?)
            """, (f"-{self.max_ttl} seconds",))
            conn.commit()
            
    def calculate_ttl(
        self,
        validation_score: int
    ) -> int:
        """Calculate TTL based on validation score"""
        # Higher scores get longer TTL
        base_ttl = self.min_ttl + (
            (self.max_ttl - self.min_ttl) *
            (validation_score / 100)
        )
        return int(min(base_ttl, self.max_ttl))
        
    async def get_statistics(self) -> Dict[str, Any]:
        """Get validation statistics"""
        async with self._get_connection() as conn:
            stats = {}
            
            # Total validations
            cursor = conn.execute("SELECT COUNT(*) FROM validations")
            stats['total_validations'] = cursor.fetchone()[0]
            
            # Valid ratio
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) * 100.0 / NULLIF(COUNT(*), 0)
                FROM validations 
                WHERE is_valid = 1
            """)
            stats['valid_ratio'] = cursor.fetchone()[0] or 0
            
            # Average score
            cursor = conn.execute("""
                SELECT AVG(validation_score)
                FROM validations
            """)
            stats['avg_score'] = cursor.fetchone()[0] or 0
            
            # Chain distribution
            cursor = conn.execute("""
                SELECT chain, COUNT(*)
                FROM validations
                GROUP BY chain
            """)
            stats['chain_distribution'] = dict(cursor.fetchall())
            
            # Recent validations (last hour)
            cursor = conn.execute("""
                SELECT COUNT(*)
                FROM validations
                WHERE datetime(timestamp) > datetime('now', '-1 hour')
            """)
            stats['recent_validations'] = cursor.fetchone()[0]
            
            return stats
