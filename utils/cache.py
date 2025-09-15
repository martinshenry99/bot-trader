"""
Cache utility for Meme Trader V4 Pro
"""

import time
import threading
from functools import wraps
from typing import Any, Dict, Optional

class TTLCache:
    def __init__(self, ttl=600):
        self.ttl = ttl
        self.cache = {}
        self.lock = threading.Lock()

    def set(self, key, value):
        with self.lock:
            self.cache[key] = (value, time.time())

    def get(self, key):
        with self.lock:
            item = self.cache.get(key)
            if not item:
                return None
            value, ts = item
            if time.time() - ts > self.ttl:
                del self.cache[key]
                return None
            return value

    def invalidate(self, key):
        with self.lock:
            if key in self.cache:
                del self.cache[key]

    def clear(self):
        with self.lock:
            self.cache.clear()

cache = TTLCache()

def cache_result(ttl: int = 300):
    """Cache function results with TTL"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            result = cache.get(key)
            
            if result is None:
                result = await func(*args, **kwargs)
                if result is not None:
                    cache.set(key, result)
            
            return result
        return wrapper
    return decorator
