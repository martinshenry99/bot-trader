"""
Caching layer for the trading bot to optimize API calls and data access.
"""
from typing import Any, Dict, Optional, Union
from datetime import datetime, timedelta
import json
import asyncio
from functools import wraps

class CacheManager:
    """Manages caching for token data, API responses, and analysis results"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        
        # Default TTLs for different data types (in seconds)
        self.ttls = {
            'price': 60,          # 1 minute for prices
            'balance': 300,       # 5 minutes for balances
            'security': 1800,     # 30 minutes for security analysis
            'metadata': 3600,     # 1 hour for token metadata
            'health': 60,         # 1 minute for health checks
            'portfolio': 300      # 5 minutes for portfolio data
        }
    
    async def get(self, key: str, category: str = 'default') -> Optional[Any]:
        """Get value from cache if not expired"""
        if key not in self._cache:
            return None
            
        entry = self._cache[key]
        if self._is_expired(entry, category):
            await self.delete(key)
            return None
            
        return entry['value']
    
    async def set(
        self,
        key: str,
        value: Any,
        category: str = 'default',
        ttl: Optional[int] = None
    ):
        """Set cache value with TTL"""
        lock = self._get_lock(key)
        async with lock:
            self._cache[key] = {
                'value': value,
                'timestamp': datetime.utcnow().timestamp(),
                'category': category,
                'ttl': ttl or self.ttls.get(category, 300)
            }
    
    async def delete(self, key: str):
        """Remove item from cache"""
        lock = self._get_lock(key)
        async with lock:
            if key in self._cache:
                del self._cache[key]
            if key in self._locks:
                del self._locks[key]
    
    async def clear(self, category: Optional[str] = None):
        """Clear all or category-specific cache entries"""
        keys_to_delete = []
        for key, entry in self._cache.items():
            if not category or entry['category'] == category:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            await self.delete(key)
    
    def _is_expired(self, entry: Dict[str, Any], category: str) -> bool:
        """Check if cache entry is expired"""
        now = datetime.utcnow().timestamp()
        age = now - entry['timestamp']
        ttl = entry['ttl'] or self.ttls.get(category, 300)
        return age > ttl
    
    def _get_lock(self, key: str) -> asyncio.Lock:
        """Get or create lock for cache key"""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            'total_entries': len(self._cache),
            'categories': {},
            'memory_usage': 0
        }
        
        for entry in self._cache.values():
            cat = entry['category']
            if cat not in stats['categories']:
                stats['categories'][cat] = 0
            stats['categories'][cat] += 1
            
            # Rough memory estimation
            stats['memory_usage'] += len(json.dumps(entry['value']))
        
        return stats

def cached(category: str, key_prefix: str = ''):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
            cache_key = ':'.join(key_parts)
            
            # Try getting from cache
            cache_result = await self.cache.get(cache_key, category)
            if cache_result is not None:
                return cache_result
            
            # Get fresh result
            result = await func(self, *args, **kwargs)
            
            # Cache the result
            await self.cache.set(cache_key, result, category)
            
            return result
        return wrapper
    return decorator
