"""
Core reliability components for error handling, caching, and rate limiting
"""
from typing import Any, Callable, Dict, Optional, TypeVar, Union
from datetime import datetime, timedelta
import asyncio
import logging
import time
from functools import wraps
from dataclasses import dataclass
import aiohttp
import redis
from ratelimit import limits, RateLimitException
import backoff

# Type variables for generics
T = TypeVar('T')
CacheKey = Union[str, int]

logger = logging.getLogger(__name__)

@dataclass
class APIConfig:
    """API configuration and limits"""
    name: str
    calls_per_minute: int
    retry_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    cache_ttl: int = 300  # 5 minutes

class APIError(Exception):
    """Base exception for API errors"""
    def __init__(self, api_name: str, message: str, status_code: Optional[int] = None):
        self.api_name = api_name
        self.status_code = status_code
        super().__init__(f"{api_name} API Error: {message}")

class RateLimitExceeded(APIError):
    """Rate limit exceeded exception"""
    pass

class ServiceUnavailable(APIError):
    """Service temporarily unavailable"""
    pass

class ValidationError(APIError):
    """Validation error from API"""
    pass

class Cache:
    """TTL-based caching using Redis"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = redis.Redis.from_url(
            redis_url,
            decode_responses=True
        )
        
    async def get(self, key: CacheKey) -> Optional[str]:
        """Get value from cache"""
        try:
            return self.redis.get(str(key))
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None
            
    async def set(
        self,
        key: CacheKey,
        value: str,
        ttl: int
    ) -> bool:
        """Set value in cache with TTL"""
        try:
            return bool(
                self.redis.setex(
                    str(key),
                    ttl,
                    value
                )
            )
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False
            
    async def delete(self, key: CacheKey) -> bool:
        """Delete key from cache"""
        try:
            return bool(self.redis.delete(str(key)))
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False

class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(
        self,
        calls_per_minute: int,
        burst_size: Optional[int] = None
    ):
        self.calls_per_minute = calls_per_minute
        self.burst_size = burst_size or calls_per_minute
        self.tokens = self.burst_size
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()
        
    async def acquire(self) -> bool:
        """Acquire a token, return True if successful"""
        async with self.lock:
            now = time.monotonic()
            # Refill tokens based on time passed
            time_passed = now - self.last_update
            new_tokens = time_passed * (self.calls_per_minute / 60.0)
            self.tokens = min(
                self.burst_size,
                self.tokens + new_tokens
            )
            self.last_update = now
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False

class APIManager:
    """Manages API interactions with reliability features"""
    
    def __init__(
        self,
        config: APIConfig,
        cache: Optional[Cache] = None
    ):
        self.config = config
        self.cache = cache
        self.rate_limiter = RateLimiter(config.calls_per_minute)
        
    async def _should_retry(
        self,
        exception: Exception
    ) -> bool:
        """Determine if request should be retried"""
        if isinstance(exception, aiohttp.ClientError):
            if isinstance(exception, aiohttp.ClientResponseError):
                # Retry on 5xx errors or specific 4xx errors
                return 500 <= exception.status < 600 or \
                       exception.status in {429, 408}
            return True
        return False
        
    def _get_backoff_time(
        self,
        tries: int
    ) -> float:
        """Calculate backoff time with jitter"""
        base = min(
            self.config.max_delay,
            self.config.base_delay * (2 ** (tries - 1))
        )
        return base * (0.5 + time.random())
        
    async def execute_with_reliability(
        self,
        operation: Callable[..., T],
        *args,
        cache_key: Optional[CacheKey] = None,
        **kwargs
    ) -> T:
        """Execute operation with full reliability features"""
        
        # Check cache first
        if cache_key and self.cache:
            cached_result = await self.cache.get(cache_key)
            if cached_result:
                return cached_result
                
        # Check rate limit
        if not await self.rate_limiter.acquire():
            raise RateLimitExceeded(
                self.config.name,
                "Rate limit exceeded"
            )
            
        # Execute with retries
        for attempt in range(self.config.retry_attempts):
            try:
                result = await operation(*args, **kwargs)
                
                # Cache successful result
                if cache_key and self.cache:
                    await self.cache.set(
                        cache_key,
                        str(result),
                        self.config.cache_ttl
                    )
                    
                return result
                
            except Exception as e:
                logger.warning(
                    f"{self.config.name} API call failed: {str(e)}"
                )
                
                if attempt == self.config.retry_attempts - 1:
                    raise APIError(
                        self.config.name,
                        f"All retry attempts failed: {str(e)}"
                    )
                    
                if await self._should_retry(e):
                    backoff_time = self._get_backoff_time(attempt + 1)
                    logger.info(
                        f"Retrying {self.config.name} API call "
                        f"in {backoff_time:.1f}s"
                    )
                    await asyncio.sleep(backoff_time)
                else:
                    raise

def with_reliability(
    api_name: str,
    cache_key_template: Optional[str] = None
):
    """Decorator to add reliability features to API calls"""
    
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Get API config
            config = getattr(self, f"{api_name}_config", None)
            if not config:
                config = APIConfig(api_name, 60)  # Default limits
                
            # Generate cache key if template provided
            cache_key = None
            if cache_key_template:
                try:
                    cache_key = cache_key_template.format(*args, **kwargs)
                except Exception as e:
                    logger.warning(
                        f"Failed to generate cache key: {e}"
                    )
                    
            # Create API manager
            api_manager = APIManager(
                config,
                getattr(self, 'cache', None)
            )
            
            # Execute with reliability
            return await api_manager.execute_with_reliability(
                func,
                self,
                *args,
                cache_key=cache_key,
                **kwargs
            )
            
        return wrapper
    return decorator
