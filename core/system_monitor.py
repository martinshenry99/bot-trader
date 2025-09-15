"""
System monitoring and diagnostics for the trading bot.
"""
from typing import Dict, Any
import time
import asyncio
import psutil
from datetime import datetime, timedelta

from .cache_manager import CacheManager
from db.models import Trade, Alert, WatchlistToken
from integrations.base import BaseAPI
from integrations.coingecko import CoinGeckoAPI
from integrations.covalent import CovalentAPI
from integrations.goplus import GoPlusAPI
from integrations.helius import HeliusAPI
from integrations.jupiter import JupiterAPI
from integrations.zerox import ZeroXClient

class SystemMonitor:
    """Monitors system health and performance metrics"""
    
    def __init__(
        self,
        cache: CacheManager,
        apis: Dict[str, BaseAPI]
    ):
        self.cache = cache
        self.apis = apis
        self._start_time = time.time()
        self._last_scan = None
        self._api_stats = {}
        self._rate_limits = {}
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            'uptime': self._get_uptime(),
            'system': await self._get_system_metrics(),
            'api_health': await self._check_api_health(),
            'cache_stats': await self.cache.get_stats(),
            'db_stats': await self._get_db_stats(),
            'performance': await self._get_performance_metrics()
        }
    
    def _get_uptime(self) -> Dict[str, Any]:
        """Get system uptime information"""
        uptime_seconds = time.time() - self._start_time
        return {
            'started_at': datetime.fromtimestamp(self._start_time).isoformat(),
            'uptime_seconds': int(uptime_seconds),
            'uptime_formatted': str(timedelta(seconds=int(uptime_seconds)))
        }
    
    async def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system resource usage metrics"""
        process = psutil.Process()
        memory = process.memory_info()
        
        return {
            'cpu_percent': process.cpu_percent(),
            'memory_used_mb': memory.rss / (1024 * 1024),
            'thread_count': process.num_threads(),
            'open_files': len(process.open_files()),
            'connections': len(process.connections())
        }
    
    async def _check_api_health(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all integrated APIs"""
        health = {}
        
        for name, api in self.apis.items():
            try:
                # Get cached health status
                cache_key = f"health:{name}"
                cached_health = await self.cache.get(cache_key, 'health')
                
                if cached_health:
                    health[name] = cached_health
                    continue
                
                # Check API health
                start_time = time.time()
                is_healthy = await api.check_health()
                latency = (time.time() - start_time) * 1000
                
                status = {
                    'status': 'healthy' if is_healthy else 'unhealthy',
                    'latency_ms': round(latency, 2),
                    'rate_limit': self._rate_limits.get(name, {}),
                    'last_error': self._api_stats.get(name, {}).get('last_error'),
                    'error_count': self._api_stats.get(name, {}).get('error_count', 0)
                }
                
                # Cache health status
                await self.cache.set(cache_key, status, 'health')
                health[name] = status
                
            except Exception as e:
                health[name] = {
                    'status': 'error',
                    'error': str(e),
                    'last_error': datetime.utcnow().isoformat()
                }
                
                # Update error stats
                if name not in self._api_stats:
                    self._api_stats[name] = {'error_count': 0}
                self._api_stats[name]['error_count'] += 1
                self._api_stats[name]['last_error'] = str(e)
        
        return health
    
    async def _get_db_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        # These would be replaced with actual DB queries
        return {
            'trades_count': await Trade.count(),
            'alerts_count': await Alert.count(),
            'watchlist_count': await WatchlistToken.count(),
            'last_trade': await Trade.get_latest(),
            'index_stats': await self._get_index_stats()
        }
    
    async def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        return {
            'last_scan_time': self._last_scan,
            'last_scan_duration': self._api_stats.get('scan_duration'),
            'average_response_time': self._calculate_avg_response(),
            'rate_limits': self._rate_limits,
            'error_rates': self._calculate_error_rates()
        }
    
    async def _get_index_stats(self) -> Dict[str, Any]:
        """Get database index statistics"""
        # This would be replaced with actual DB queries
        return {
            'trades_indexes': [
                {'name': 'idx_trades_user', 'size': '1.2MB'},
                {'name': 'idx_trades_token', 'size': '800KB'}
            ],
            'alerts_indexes': [
                {'name': 'idx_alerts_user', 'size': '500KB'},
                {'name': 'idx_alerts_token', 'size': '400KB'}
            ],
            'watchlist_indexes': [
                {'name': 'idx_watchlist_user', 'size': '300KB'},
                {'name': 'idx_watchlist_token', 'size': '250KB'}
            ]
        }
    
    def _calculate_avg_response(self) -> Dict[str, float]:
        """Calculate average response times for APIs"""
        avg_times = {}
        for name, stats in self._api_stats.items():
            if 'response_times' in stats:
                times = stats['response_times']
                if times:
                    avg_times[name] = sum(times) / len(times)
        return avg_times
    
    def _calculate_error_rates(self) -> Dict[str, float]:
        """Calculate error rates for APIs"""
        error_rates = {}
        for name, stats in self._api_stats.items():
            total = stats.get('total_requests', 0)
            errors = stats.get('error_count', 0)
            if total > 0:
                error_rates[name] = (errors / total) * 100
        return error_rates
    
    def update_scan_time(self, duration: float):
        """Update last scan time and duration"""
        self._last_scan = datetime.utcnow().isoformat()
        self._api_stats['scan_duration'] = duration
    
    def update_rate_limit(self, api_name: str, limit: Dict[str, Any]):
        """Update rate limit info for an API"""
        self._rate_limits[api_name] = limit
    
    def log_api_call(
        self,
        api_name: str,
        duration: float,
        success: bool,
        error: str = None
    ):
        """Log API call statistics"""
        if api_name not in self._api_stats:
            self._api_stats[api_name] = {
                'total_requests': 0,
                'error_count': 0,
                'response_times': []
            }
        
        stats = self._api_stats[api_name]
        stats['total_requests'] += 1
        stats['response_times'].append(duration)
        
        # Keep last 100 response times
        if len(stats['response_times']) > 100:
            stats['response_times'].pop(0)
        
        if not success:
            stats['error_count'] += 1
            stats['last_error'] = error
