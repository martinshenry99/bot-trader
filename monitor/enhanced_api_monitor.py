"""
Enhanced API monitoring with database storage, alerts and circuit breaker
"""
import os
import json
import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import aiohttp

from db.models import DB_PATH
from handlers.telegram_handler import send_telegram_alert

logger = logging.getLogger(__name__)

class CircuitBreakerState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"

class EnhancedAPIMonitor:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        
    def _init_db(self):
        """Initialize database tables if they don't exist"""
        with self.conn:
            self.conn.execute('''
            CREATE TABLE IF NOT EXISTS api_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                latency REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                response_data TEXT
            )''')
            
            self.conn.execute('''
            CREATE TABLE IF NOT EXISTS rate_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api TEXT UNIQUE NOT NULL,
                limit_value INTEGER NOT NULL,
                window INTEGER NOT NULL,
                current_usage INTEGER DEFAULT 0,
                last_reset DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
            
            self.conn.execute('''
            CREATE TABLE IF NOT EXISTS circuit_breakers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api TEXT UNIQUE NOT NULL,
                state TEXT NOT NULL,
                failure_count INTEGER DEFAULT 0,
                last_failure DATETIME,
                cooldown_period INTEGER DEFAULT 300,
                threshold INTEGER DEFAULT 5
            )''')
            
    async def can_make_request(self, api: str) -> bool:
        """Check if request can be made based on circuit breaker state"""
        with self.conn:
            cursor = self.conn.execute(
                'SELECT * FROM circuit_breakers WHERE api = ?',
                (api,)
            )
            breaker = cursor.fetchone()
            
            if not breaker:
                self.conn.execute(
                    '''INSERT INTO circuit_breakers 
                    (api, state, failure_count, cooldown_period, threshold)
                    VALUES (?, 'closed', 0, 300, 5)''',
                    (api,)
                )
                return True
            
        if breaker.state == CircuitBreakerState.OPEN:
            if breaker.last_failure:
                cooldown_end = breaker.last_failure + timedelta(seconds=breaker.cooldown_period)
                if datetime.utcnow() >= cooldown_end:
                    breaker.state = CircuitBreakerState.HALF_OPEN
                    self.session.commit()
                else:
                    return False
                    
        return True
        
    def track_request(
        self,
        api: str,
        endpoint: str,
        status_code: int,
        latency: float,
        response_data: Optional[dict] = None
    ):
        """Track API request with database storage"""
        with self.conn:
            # Record request
            self.conn.execute(
                '''INSERT INTO api_requests 
                (api, endpoint, status_code, latency, timestamp, response_data)
                VALUES (?, ?, ?, ?, ?, ?)''',
                (
                    api,
                    endpoint,
                    status_code,
                    latency,
                    datetime.utcnow().isoformat(),
                    json.dumps(response_data) if response_data else None
                )
            )
        
        # Update rate limit usage
        rate_limit = self.session.query(RateLimit).filter_by(api=api).first()
        if rate_limit:
            # Clean old usage data
            if rate_limit.last_reset + timedelta(seconds=rate_limit.window) < datetime.utcnow():
                rate_limit.current_usage = 1
                rate_limit.last_reset = datetime.utcnow()
            else:
                rate_limit.current_usage += 1
                
            # Check rate limit threshold
            usage_percent = (rate_limit.current_usage / rate_limit.limit) * 100
            if usage_percent >= 80:
                asyncio.create_task(self._send_rate_limit_alert(api, usage_percent))
                
        # Update circuit breaker
        breaker = self.circuit_breakers.get(api)
        if breaker:
            if status_code >= 500:
                breaker.failure_count += 1
                breaker.last_failure = datetime.utcnow()
                
                if breaker.state == CircuitBreakerState.HALF_OPEN:
                    breaker.state = CircuitBreakerState.OPEN
                    asyncio.create_task(self._send_circuit_breaker_alert(api, "opened"))
                elif breaker.failure_count >= breaker.threshold:
                    breaker.state = CircuitBreakerState.OPEN
                    asyncio.create_task(self._send_circuit_breaker_alert(api, "opened"))
            else:
                if breaker.state == CircuitBreakerState.HALF_OPEN:
                    breaker.state = CircuitBreakerState.CLOSED
                    breaker.failure_count = 0
                    asyncio.create_task(self._send_circuit_breaker_alert(api, "closed"))
                    
        self.session.commit()
        
    async def _send_rate_limit_alert(self, api: str, usage_percent: float):
        """Send rate limit alert via Telegram"""
        message = (
            f"⚠️ High API Usage Alert\n"
            f"API: {api}\n"
            f"Usage: {usage_percent:.1f}%\n"
            f"Time: {datetime.utcnow().isoformat()}"
        )
        await send_telegram_alert(message)
        
    async def _send_circuit_breaker_alert(self, api: str, state: str):
        """Send circuit breaker state change alert"""
        message = (
            f"🔌 Circuit Breaker Alert\n"
            f"API: {api}\n"
            f"State: {state}\n"
            f"Time: {datetime.utcnow().isoformat()}"
        )
        await send_telegram_alert(message)
        
    def get_api_metrics(self, api: str, window_hours: int = 24) -> Dict[str, Any]:
        """Get API metrics from database"""
        since = datetime.utcnow() - timedelta(hours=window_hours)
        
        # Get request statistics
        stats = self.session.query(
            func.count().label('total_requests'),
            func.avg(APIRequest.latency).label('avg_latency'),
            func.sum(case((APIRequest.status_code >= 400, 1), else_=0)).label('errors')
        ).filter(
            APIRequest.api == api,
            APIRequest.timestamp >= since
        ).first()
        
        # Get rate limit info
        rate_limit = self.session.query(RateLimit).filter_by(api=api).first()
        
        # Get circuit breaker state
        breaker = self.circuit_breakers.get(api)
        
        return {
            "total_requests": stats.total_requests or 0,
            "error_rate": (stats.errors / stats.total_requests * 100) if stats.total_requests else 0,
            "avg_latency": stats.avg_latency or 0,
            "rate_limit_status": {
                "current_usage": rate_limit.current_usage if rate_limit else 0,
                "limit": rate_limit.limit if rate_limit else 0
            } if rate_limit else None,
            "circuit_breaker": {
                "state": breaker.state,
                "failure_count": breaker.failure_count
            } if breaker else None
        }
        
    async def monitor_rate_limits(self):
        """Continuously monitor rate limits"""
        while True:
            try:
                rate_limits = self.session.query(RateLimit).all()
                for limit in rate_limits:
                    usage_percent = (limit.current_usage / limit.limit) * 100
                    if usage_percent > 80:
                        await self._send_rate_limit_alert(limit.api, usage_percent)
                        
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Rate limit monitoring error: {e}")
                await asyncio.sleep(5)
                
    def cleanup_old_data(self, days: int = 30):
        """Cleanup old request data"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        self.session.query(APIRequest).filter(
            APIRequest.timestamp < cutoff
        ).delete()
        self.session.commit()
