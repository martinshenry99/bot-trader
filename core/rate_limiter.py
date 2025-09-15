"""
Rate limiter for managing API calls and preventing rate limit errors
"""
from typing import Dict, Optional, List
import time
import asyncio
from datetime import datetime, timedelta
import logging
from functools import wraps

logger = logging.getLogger(__name__)

class TokenBucket:
    """Token bucket rate limiter implementation"""
    
    def __init__(
        self,
        rate: float,
        capacity: int,
        initial_tokens: Optional[int] = None
    ):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = initial_tokens or capacity
        self.last_update = time.time()
    
    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from the bucket"""
        now = time.time()
        
        # Add new tokens based on time passed
        time_passed = now - self.last_update
        self.tokens = min(
            self.capacity,
            self.tokens + time_passed * self.rate
        )
        self.last_update = now
        
        # Try to consume tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
            
        return False

class RateLimiter:
    """Rate limiter for API calls"""
    
    def __init__(self):
        self._buckets: Dict[str, TokenBucket] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        
        # Default rate limits
        self.default_limits = {
            'covalent': (5, 10),    # 5 calls/sec, burst of 10
            'helius': (10, 20),     # 10 calls/sec, burst of 20
            'goplus': (3, 5),       # 3 calls/sec, burst of 5
            'coingecko': (10, 30),  # 10 calls/sec, burst of 30
            'zerox': (5, 10),       # 5 calls/sec, burst of 10
            'jupiter': (10, 20)     # 10 calls/sec, burst of 20
        }
        
        # Initialize default buckets
        for service, (rate, capacity) in self.default_limits.items():
            self.add_bucket(service, rate, capacity)
    
    def add_bucket(
        self,
        name: str,
        rate: float,
        capacity: int,
        initial_tokens: Optional[int] = None
    ):
        """Add a new rate limit bucket"""
        self._buckets[name] = TokenBucket(rate, capacity, initial_tokens)
        self._locks[name] = asyncio.Lock()
    
    def update_limits(
        self,
        service: str,
        rate: float,
        capacity: int
    ):
        """Update rate limits for a service"""
        self.add_bucket(service, rate, capacity)
    
    async def acquire(
        self,
        service: str,
        tokens: int = 1,
        timeout: Optional[float] = None
    ) -> bool:
        """Acquire permission to make API calls"""
        if service not in self._buckets:
            logger.warning(f"No rate limit bucket for {service}, using default")
            rate, capacity = self.default_limits.get(
                service,
                (1, 1)  # Very restrictive default
            )
            self.add_bucket(service, rate, capacity)
        
        bucket = self._buckets[service]
        lock = self._locks[service]
        
        start_time = time.time()
        while True:
            async with lock:
                if bucket.consume(tokens):
                    return True
            
            if timeout is not None:
                if time.time() - start_time > timeout:
                    return False
            
            # Wait before trying again
            await asyncio.sleep(1.0 / bucket.rate)
    
    def rate_limited(
        self,
        service: str,
        tokens: int = 1,
        timeout: Optional[float] = None
    ):
        """Decorator for rate-limited API calls"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                acquired = await self.acquire(service, tokens, timeout)
                if not acquired:
                    raise Exception(f"Rate limit exceeded for {service}")
                return await func(*args, **kwargs)
            return wrapper
        return decorator

# Global instance
rate_limiter = RateLimiter()

# Example usage:
"""
@rate_limiter.rate_limited('coingecko')
async def get_token_price(token_id: str):
    # API call implementation
    pass

# Or manual usage:
async def make_api_call():
    if await rate_limiter.acquire('helius'):
        # Make API call
        pass
"""
