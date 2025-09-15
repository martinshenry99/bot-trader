"""
API error handling and rate limiting 
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)

class APIError(Exception):
    """Base class for API errors"""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"{status_code}: {message}")

class RateLimitError(APIError):
    """Rate limit exceeded error"""
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(429, f"Rate limit exceeded, retry after {retry_after}s")

class APIManager:
    """Manages API calls with rate limiting and error handling"""
    
    def __init__(self):
        self.rate_limits: Dict[str, Dict[str, Any]] = {}
        self.call_counts: Dict[str, int] = {}
        self.last_reset: Dict[str, datetime] = {}
        
    async def handle_rate_limit(
        self,
        api_key: str,
        service: str,
        max_calls: int,
        window_seconds: int
    ) -> None:
        """Handle rate limiting for an API call"""
        now = datetime.utcnow()
        
        # Initialize or reset counters
        if service not in self.last_reset:
            self.last_reset[service] = now
            self.call_counts[service] = 0
        elif (now - self.last_reset[service]).total_seconds() > window_seconds:
            self.last_reset[service] = now
            self.call_counts[service] = 0
            
        # Check rate limit
        if self.call_counts[service] >= max_calls:
            seconds_to_reset = window_seconds - (now - self.last_reset[service]).total_seconds()
            raise RateLimitError(int(seconds_to_reset))
            
        # Increment counter
        self.call_counts[service] += 1
        
    def rate_limit(
        self,
        service: str,
        max_calls: int,
        window_seconds: int
    ) -> Callable:
        """Decorator for rate limiting API calls"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs) -> Any:
                api_key = kwargs.get('api_key', 'default')
                
                try:
                    await self.handle_rate_limit(
                        api_key,
                        service,
                        max_calls,
                        window_seconds
                    )
                    return await func(*args, **kwargs)
                    
                except RateLimitError as e:
                    logger.warning(f"Rate limit exceeded for {service}: {e}")
                    # Wait and retry
                    await asyncio.sleep(e.retry_after)
                    return await func(*args, **kwargs)
                    
                except Exception as e:
                    logger.error(f"API call failed: {e}")
                    raise
                    
            return wrapper
        return decorator

api_manager = APIManager()
